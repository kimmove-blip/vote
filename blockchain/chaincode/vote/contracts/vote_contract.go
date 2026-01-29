/*
 * Vote Contract - Hyperledger Fabric Chaincode for Secure Voting
 *
 * This chaincode implements the core voting functionality:
 * - CastVote: Record encrypted votes with ZKP verification
 * - GetVote: Retrieve vote records
 * - GetAllVotes: Get all votes for an election
 * - VerifyVote: Verify vote existence and integrity
 * - StoreTallyResult: Record tally results
 * - GetTallyResult: Retrieve tally results
 */

package contracts

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"time"

	"github.com/hyperledger/fabric-contract-api-go/contractapi"
)

// VoteContract implements the voting chaincode
type VoteContract struct {
	contractapi.Contract
}

// Vote represents an encrypted vote record
type Vote struct {
	ElectionID          string    `json:"electionId"`
	EncryptedVote       string    `json:"encryptedVote"`
	EncryptedVoteHash   string    `json:"encryptedVoteHash"`
	Nullifier           string    `json:"nullifier"`
	EligibilityProofHash string   `json:"eligibilityProofHash"`
	ValidityProofHash   string    `json:"validityProofHash"`
	Timestamp           time.Time `json:"timestamp"`
	TxID                string    `json:"txId"`
	BlockNumber         uint64    `json:"blockNumber"`
}

// VoteReceipt is returned after a successful vote
type VoteReceipt struct {
	Success           bool      `json:"success"`
	VerificationCode  string    `json:"verificationCode"`
	EncryptedVoteHash string    `json:"encryptedVoteHash"`
	TxID              string    `json:"txId"`
	BlockNumber       uint64    `json:"blockNumber"`
	Timestamp         time.Time `json:"timestamp"`
}

// Election represents an election configuration
type Election struct {
	ID              string    `json:"id"`
	Title           string    `json:"title"`
	Status          string    `json:"status"`
	VoterMerkleRoot string    `json:"voterMerkleRoot"`
	PublicKey       string    `json:"publicKey"`
	StartTime       time.Time `json:"startTime"`
	EndTime         time.Time `json:"endTime"`
	CreatedAt       time.Time `json:"createdAt"`
}

// TallyResult represents the tally for an election
type TallyResult struct {
	ElectionID          string         `json:"electionId"`
	VoteCounts          map[string]int `json:"voteCounts"`
	TotalVotes          int            `json:"totalVotes"`
	AggregatedHash      string         `json:"aggregatedHash"`
	DecryptionProof     string         `json:"decryptionProof"`
	TallyTimestamp      time.Time      `json:"tallyTimestamp"`
	TxID                string         `json:"txId"`
}

// BulletinBoardEntry represents a public bulletin board entry
type BulletinBoardEntry struct {
	Sequence    int       `json:"sequence"`
	Type        string    `json:"type"`
	Hash        string    `json:"hash"`
	TxID        string    `json:"txId"`
	Timestamp   time.Time `json:"timestamp"`
}

// InitLedger initializes the chaincode
func (v *VoteContract) InitLedger(ctx contractapi.TransactionContextInterface) error {
	fmt.Println("Vote Contract initialized")
	return nil
}

// CreateElection creates a new election on the blockchain
func (v *VoteContract) CreateElection(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	title string,
	voterMerkleRoot string,
	publicKey string,
	startTimeStr string,
	endTimeStr string,
) error {
	// Check if election already exists
	existing, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return fmt.Errorf("failed to read election: %v", err)
	}
	if existing != nil {
		return fmt.Errorf("election %s already exists", electionID)
	}

	// Parse times
	startTime, err := time.Parse(time.RFC3339, startTimeStr)
	if err != nil {
		return fmt.Errorf("invalid start time: %v", err)
	}
	endTime, err := time.Parse(time.RFC3339, endTimeStr)
	if err != nil {
		return fmt.Errorf("invalid end time: %v", err)
	}

	election := Election{
		ID:              electionID,
		Title:           title,
		Status:          "pending",
		VoterMerkleRoot: voterMerkleRoot,
		PublicKey:       publicKey,
		StartTime:       startTime,
		EndTime:         endTime,
		CreatedAt:       time.Now(),
	}

	electionJSON, err := json.Marshal(election)
	if err != nil {
		return err
	}

	// Store election
	if err := ctx.GetStub().PutState(electionKey(electionID), electionJSON); err != nil {
		return err
	}

	// Add to bulletin board
	return v.addBulletinBoardEntry(ctx, electionID, "election_created", hashString(string(electionJSON)))
}

// ActivateElection activates an election for voting
func (v *VoteContract) ActivateElection(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) error {
	electionJSON, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return fmt.Errorf("failed to read election: %v", err)
	}
	if electionJSON == nil {
		return fmt.Errorf("election %s does not exist", electionID)
	}

	var election Election
	if err := json.Unmarshal(electionJSON, &election); err != nil {
		return err
	}

	if election.Status != "pending" {
		return fmt.Errorf("election is not in pending status")
	}

	election.Status = "active"

	updatedJSON, err := json.Marshal(election)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(electionKey(electionID), updatedJSON)
}

// CastVote records an encrypted vote on the blockchain
// This is the core voting function
func (v *VoteContract) CastVote(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	encryptedVote string,
	nullifier string,
	eligibilityProofHash string,
	validityProofHash string,
) (*VoteReceipt, error) {
	// 1. Verify election exists and is active
	electionJSON, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return nil, fmt.Errorf("failed to read election: %v", err)
	}
	if electionJSON == nil {
		return nil, fmt.Errorf("election %s does not exist", electionID)
	}

	var election Election
	if err := json.Unmarshal(electionJSON, &election); err != nil {
		return nil, err
	}

	if election.Status != "active" {
		return nil, fmt.Errorf("election is not active (current status: %s)", election.Status)
	}

	// Check time bounds
	now := time.Now()
	if now.Before(election.StartTime) {
		return nil, fmt.Errorf("election has not started yet")
	}
	if now.After(election.EndTime) {
		return nil, fmt.Errorf("election has ended")
	}

	// 2. Check nullifier hasn't been used (double-voting prevention)
	nullifierKey := voteKey(electionID, nullifier)
	existingVote, err := ctx.GetStub().GetState(nullifierKey)
	if err != nil {
		return nil, fmt.Errorf("failed to check nullifier: %v", err)
	}
	if existingVote != nil {
		return nil, fmt.Errorf("vote already submitted (duplicate nullifier)")
	}

	// 3. Verify ZKP proofs (off-chain verification assumed)
	// In production, integrate with a ZKP verifier contract or library
	// The proofs are verified by the backend before submission

	// 4. Compute encrypted vote hash
	encryptedVoteHash := hashString(encryptedVote)

	// 5. Get transaction context
	txID := ctx.GetStub().GetTxID()
	txTimestamp, err := ctx.GetStub().GetTxTimestamp()
	if err != nil {
		return nil, fmt.Errorf("failed to get timestamp: %v", err)
	}
	timestamp := time.Unix(txTimestamp.Seconds, int64(txTimestamp.Nanos))

	// 6. Create vote record
	vote := Vote{
		ElectionID:          electionID,
		EncryptedVote:       encryptedVote,
		EncryptedVoteHash:   encryptedVoteHash,
		Nullifier:           nullifier,
		EligibilityProofHash: eligibilityProofHash,
		ValidityProofHash:   validityProofHash,
		Timestamp:           timestamp,
		TxID:                txID,
		BlockNumber:         0, // Will be set after block confirmation
	}

	voteJSON, err := json.Marshal(vote)
	if err != nil {
		return nil, err
	}

	// 7. Store vote
	if err := ctx.GetStub().PutState(nullifierKey, voteJSON); err != nil {
		return nil, fmt.Errorf("failed to store vote: %v", err)
	}

	// 8. Update vote index for the election
	if err := v.addVoteToIndex(ctx, electionID, nullifier); err != nil {
		return nil, fmt.Errorf("failed to update vote index: %v", err)
	}

	// 9. Add to bulletin board
	if err := v.addBulletinBoardEntry(ctx, electionID, "vote_cast", encryptedVoteHash); err != nil {
		return nil, fmt.Errorf("failed to update bulletin board: %v", err)
	}

	// 10. Emit event
	eventPayload := map[string]string{
		"electionId":        electionID,
		"encryptedVoteHash": encryptedVoteHash,
		"txId":              txID,
	}
	eventJSON, _ := json.Marshal(eventPayload)
	if err := ctx.GetStub().SetEvent("VoteCast", eventJSON); err != nil {
		return nil, fmt.Errorf("failed to emit event: %v", err)
	}

	// 11. Generate verification code
	verificationCode := generateVerificationCode(txID, encryptedVoteHash)

	// 12. Return receipt
	return &VoteReceipt{
		Success:           true,
		VerificationCode:  verificationCode,
		EncryptedVoteHash: encryptedVoteHash,
		TxID:              txID,
		BlockNumber:       0,
		Timestamp:         timestamp,
	}, nil
}

// GetVote retrieves a vote by nullifier
func (v *VoteContract) GetVote(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	nullifier string,
) (*Vote, error) {
	voteJSON, err := ctx.GetStub().GetState(voteKey(electionID, nullifier))
	if err != nil {
		return nil, fmt.Errorf("failed to read vote: %v", err)
	}
	if voteJSON == nil {
		return nil, fmt.Errorf("vote not found")
	}

	var vote Vote
	if err := json.Unmarshal(voteJSON, &vote); err != nil {
		return nil, err
	}

	return &vote, nil
}

// GetAllVotes retrieves all votes for an election
func (v *VoteContract) GetAllVotes(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) (map[string]interface{}, error) {
	// Get vote index
	indexKey := voteIndexKey(electionID)
	indexJSON, err := ctx.GetStub().GetState(indexKey)
	if err != nil {
		return nil, fmt.Errorf("failed to read vote index: %v", err)
	}

	var nullifiers []string
	if indexJSON != nil {
		if err := json.Unmarshal(indexJSON, &nullifiers); err != nil {
			return nil, err
		}
	}

	// Collect all encrypted votes
	votes := make([]string, 0, len(nullifiers))
	for _, nullifier := range nullifiers {
		voteJSON, err := ctx.GetStub().GetState(voteKey(electionID, nullifier))
		if err != nil {
			continue
		}
		if voteJSON != nil {
			var vote Vote
			if err := json.Unmarshal(voteJSON, &vote); err == nil {
				votes = append(votes, vote.EncryptedVote)
			}
		}
	}

	return map[string]interface{}{
		"votes": votes,
		"count": len(votes),
	}, nil
}

// VerifyVote verifies a vote exists and matches the provided hash
func (v *VoteContract) VerifyVote(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	nullifier string,
	expectedHash string,
) (map[string]interface{}, error) {
	vote, err := v.GetVote(ctx, electionID, nullifier)
	if err != nil {
		return map[string]interface{}{
			"verified": false,
			"error":    err.Error(),
		}, nil
	}

	verified := vote.EncryptedVoteHash == expectedHash

	return map[string]interface{}{
		"verified":   verified,
		"txId":       vote.TxID,
		"timestamp":  vote.Timestamp,
	}, nil
}

// GetVoteByHash retrieves a vote by its encrypted vote hash
func (v *VoteContract) GetVoteByHash(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	encryptedVoteHash string,
) (map[string]interface{}, error) {
	// This requires iterating through votes - in production, use a composite key index
	indexKey := voteIndexKey(electionID)
	indexJSON, err := ctx.GetStub().GetState(indexKey)
	if err != nil {
		return nil, err
	}

	var nullifiers []string
	if indexJSON != nil {
		if err := json.Unmarshal(indexJSON, &nullifiers); err != nil {
			return nil, err
		}
	}

	for _, nullifier := range nullifiers {
		voteJSON, err := ctx.GetStub().GetState(voteKey(electionID, nullifier))
		if err != nil {
			continue
		}
		if voteJSON != nil {
			var vote Vote
			if err := json.Unmarshal(voteJSON, &vote); err == nil {
				if vote.EncryptedVoteHash == encryptedVoteHash {
					return map[string]interface{}{
						"found":             true,
						"encryptedVoteHash": vote.EncryptedVoteHash,
						"txId":              vote.TxID,
						"blockNumber":       vote.BlockNumber,
						"timestamp":         vote.Timestamp,
					}, nil
				}
			}
		}
	}

	return map[string]interface{}{
		"found": false,
	}, nil
}

// CloseElection closes an election for voting
func (v *VoteContract) CloseElection(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) error {
	electionJSON, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return fmt.Errorf("failed to read election: %v", err)
	}
	if electionJSON == nil {
		return fmt.Errorf("election %s does not exist", electionID)
	}

	var election Election
	if err := json.Unmarshal(electionJSON, &election); err != nil {
		return err
	}

	if election.Status != "active" {
		return fmt.Errorf("election is not active")
	}

	election.Status = "closed"

	updatedJSON, err := json.Marshal(election)
	if err != nil {
		return err
	}

	if err := ctx.GetStub().PutState(electionKey(electionID), updatedJSON); err != nil {
		return err
	}

	return v.addBulletinBoardEntry(ctx, electionID, "election_closed", hashString(string(updatedJSON)))
}

// StoreTallyResult stores the tally result after decryption
func (v *VoteContract) StoreTallyResult(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	voteCountsJSON string,
	aggregatedHash string,
	decryptionProof string,
) error {
	// Verify election is closed
	electionJSON, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return fmt.Errorf("failed to read election: %v", err)
	}
	if electionJSON == nil {
		return fmt.Errorf("election %s does not exist", electionID)
	}

	var election Election
	if err := json.Unmarshal(electionJSON, &election); err != nil {
		return err
	}

	if election.Status != "closed" && election.Status != "tallying" {
		return fmt.Errorf("election must be closed or tallying to store results")
	}

	// Parse vote counts
	var voteCounts map[string]int
	if err := json.Unmarshal([]byte(voteCountsJSON), &voteCounts); err != nil {
		return fmt.Errorf("invalid vote counts: %v", err)
	}

	// Calculate total votes
	totalVotes := 0
	for _, count := range voteCounts {
		totalVotes += count
	}

	txID := ctx.GetStub().GetTxID()

	result := TallyResult{
		ElectionID:      electionID,
		VoteCounts:      voteCounts,
		TotalVotes:      totalVotes,
		AggregatedHash:  aggregatedHash,
		DecryptionProof: decryptionProof,
		TallyTimestamp:  time.Now(),
		TxID:            txID,
	}

	resultJSON, err := json.Marshal(result)
	if err != nil {
		return err
	}

	// Store tally result
	if err := ctx.GetStub().PutState(tallyKey(electionID), resultJSON); err != nil {
		return err
	}

	// Update election status
	election.Status = "completed"
	updatedJSON, err := json.Marshal(election)
	if err != nil {
		return err
	}
	if err := ctx.GetStub().PutState(electionKey(electionID), updatedJSON); err != nil {
		return err
	}

	// Add to bulletin board
	if err := v.addBulletinBoardEntry(ctx, electionID, "tally_completed", hashString(string(resultJSON))); err != nil {
		return err
	}

	// Emit event
	eventJSON, _ := json.Marshal(map[string]interface{}{
		"electionId": electionID,
		"totalVotes": totalVotes,
		"txId":       txID,
	})
	return ctx.GetStub().SetEvent("TallyCompleted", eventJSON)
}

// GetTallyResult retrieves the tally result for an election
func (v *VoteContract) GetTallyResult(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) (*TallyResult, error) {
	resultJSON, err := ctx.GetStub().GetState(tallyKey(electionID))
	if err != nil {
		return nil, fmt.Errorf("failed to read tally: %v", err)
	}
	if resultJSON == nil {
		return nil, fmt.Errorf("tally not found for election %s", electionID)
	}

	var result TallyResult
	if err := json.Unmarshal(resultJSON, &result); err != nil {
		return nil, err
	}

	return &result, nil
}

// GetBulletinBoard retrieves the public bulletin board for an election
func (v *VoteContract) GetBulletinBoard(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) (map[string]interface{}, error) {
	bbKey := bulletinBoardKey(electionID)
	bbJSON, err := ctx.GetStub().GetState(bbKey)
	if err != nil {
		return nil, fmt.Errorf("failed to read bulletin board: %v", err)
	}

	var entries []BulletinBoardEntry
	if bbJSON != nil {
		if err := json.Unmarshal(bbJSON, &entries); err != nil {
			return nil, err
		}
	}

	// Compute merkle root of entries
	merkleRoot := computeMerkleRoot(entries)

	return map[string]interface{}{
		"entries":    entries,
		"merkleRoot": merkleRoot,
	}, nil
}

// GetElection retrieves election details
func (v *VoteContract) GetElection(
	ctx contractapi.TransactionContextInterface,
	electionID string,
) (*Election, error) {
	electionJSON, err := ctx.GetStub().GetState(electionKey(electionID))
	if err != nil {
		return nil, fmt.Errorf("failed to read election: %v", err)
	}
	if electionJSON == nil {
		return nil, fmt.Errorf("election %s does not exist", electionID)
	}

	var election Election
	if err := json.Unmarshal(electionJSON, &election); err != nil {
		return nil, err
	}

	return &election, nil
}

// Helper functions

func electionKey(electionID string) string {
	return fmt.Sprintf("election:%s", electionID)
}

func voteKey(electionID, nullifier string) string {
	return fmt.Sprintf("vote:%s:%s", electionID, nullifier)
}

func voteIndexKey(electionID string) string {
	return fmt.Sprintf("voteindex:%s", electionID)
}

func tallyKey(electionID string) string {
	return fmt.Sprintf("tally:%s", electionID)
}

func bulletinBoardKey(electionID string) string {
	return fmt.Sprintf("bulletinboard:%s", electionID)
}

func hashString(s string) string {
	hash := sha256.Sum256([]byte(s))
	return hex.EncodeToString(hash[:])
}

func generateVerificationCode(txID, hash string) string {
	combined := txID + hash
	h := sha256.Sum256([]byte(combined))
	return hex.EncodeToString(h[:8]) // 16 character code
}

func (v *VoteContract) addVoteToIndex(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	nullifier string,
) error {
	indexKey := voteIndexKey(electionID)
	indexJSON, err := ctx.GetStub().GetState(indexKey)
	if err != nil {
		return err
	}

	var nullifiers []string
	if indexJSON != nil {
		if err := json.Unmarshal(indexJSON, &nullifiers); err != nil {
			return err
		}
	}

	nullifiers = append(nullifiers, nullifier)

	updatedJSON, err := json.Marshal(nullifiers)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(indexKey, updatedJSON)
}

func (v *VoteContract) addBulletinBoardEntry(
	ctx contractapi.TransactionContextInterface,
	electionID string,
	entryType string,
	hash string,
) error {
	bbKey := bulletinBoardKey(electionID)
	bbJSON, err := ctx.GetStub().GetState(bbKey)
	if err != nil {
		return err
	}

	var entries []BulletinBoardEntry
	if bbJSON != nil {
		if err := json.Unmarshal(bbJSON, &entries); err != nil {
			return err
		}
	}

	txID := ctx.GetStub().GetTxID()
	entry := BulletinBoardEntry{
		Sequence:  len(entries) + 1,
		Type:      entryType,
		Hash:      hash,
		TxID:      txID,
		Timestamp: time.Now(),
	}

	entries = append(entries, entry)

	updatedJSON, err := json.Marshal(entries)
	if err != nil {
		return err
	}

	return ctx.GetStub().PutState(bbKey, updatedJSON)
}

func computeMerkleRoot(entries []BulletinBoardEntry) string {
	if len(entries) == 0 {
		return ""
	}

	// Build merkle tree from entry hashes
	hashes := make([]string, len(entries))
	for i, entry := range entries {
		hashes[i] = hashString(entry.Hash + entry.TxID)
	}

	for len(hashes) > 1 {
		var newHashes []string
		for i := 0; i < len(hashes); i += 2 {
			if i+1 < len(hashes) {
				newHashes = append(newHashes, hashString(hashes[i]+hashes[i+1]))
			} else {
				newHashes = append(newHashes, hashes[i])
			}
		}
		hashes = newHashes
	}

	return hashes[0]
}
