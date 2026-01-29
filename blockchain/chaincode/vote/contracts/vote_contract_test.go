/*
 * Vote Contract Tests
 */

package contracts

import (
	"encoding/json"
	"testing"
	"time"

	"github.com/hyperledger/fabric-chaincode-go/shim"
	"github.com/hyperledger/fabric-contract-api-go/contractapi"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
)

// MockTransactionContext is a mock implementation of TransactionContextInterface
type MockTransactionContext struct {
	mock.Mock
	contractapi.TransactionContextInterface
}

type MockStub struct {
	mock.Mock
	shim.ChaincodeStubInterface
	State map[string][]byte
}

func NewMockStub() *MockStub {
	return &MockStub{
		State: make(map[string][]byte),
	}
}

func (m *MockStub) GetState(key string) ([]byte, error) {
	return m.State[key], nil
}

func (m *MockStub) PutState(key string, value []byte) error {
	m.State[key] = value
	return nil
}

func (m *MockStub) GetTxID() string {
	return "mock-tx-id-12345"
}

func (m *MockStub) GetTxTimestamp() (*timestamp.Timestamp, error) {
	return &timestamp.Timestamp{
		Seconds: time.Now().Unix(),
		Nanos:   0,
	}, nil
}

func (m *MockStub) SetEvent(name string, payload []byte) error {
	return nil
}

func (m *MockTransactionContext) GetStub() shim.ChaincodeStubInterface {
	args := m.Called()
	return args.Get(0).(shim.ChaincodeStubInterface)
}

// Test helper to create a mock election
func createMockElection() *Election {
	return &Election{
		ID:              "election-001",
		Title:           "Test Election 2024",
		Status:          "active",
		VoterMerkleRoot: "0x" + string(make([]byte, 64)),
		PublicKey:       `{"p":"123","g":"2","h":"456"}`,
		StartTime:       time.Now().Add(-1 * time.Hour),
		EndTime:         time.Now().Add(24 * time.Hour),
		CreatedAt:       time.Now().Add(-2 * time.Hour),
	}
}

func TestInitLedger(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	err := contract.InitLedger(ctx)
	assert.NoError(t, err)
}

func TestCreateElection(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	startTime := time.Now().Add(1 * time.Hour).Format(time.RFC3339)
	endTime := time.Now().Add(24 * time.Hour).Format(time.RFC3339)

	err := contract.CreateElection(
		ctx,
		"election-001",
		"Test Election",
		"0xmerkleroot",
		"publickey",
		startTime,
		endTime,
	)

	assert.NoError(t, err)

	// Verify election was stored
	stored := stub.State["election:election-001"]
	assert.NotNil(t, stored)

	var election Election
	err = json.Unmarshal(stored, &election)
	assert.NoError(t, err)
	assert.Equal(t, "Test Election", election.Title)
	assert.Equal(t, "pending", election.Status)
}

func TestCreateDuplicateElection(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	startTime := time.Now().Add(1 * time.Hour).Format(time.RFC3339)
	endTime := time.Now().Add(24 * time.Hour).Format(time.RFC3339)

	// Create first election
	_ = contract.CreateElection(ctx, "election-001", "Test", "root", "key", startTime, endTime)

	// Try to create duplicate
	err := contract.CreateElection(ctx, "election-001", "Test", "root", "key", startTime, endTime)
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "already exists")
}

func TestActivateElection(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Create election first
	election := &Election{
		ID:     "election-001",
		Title:  "Test Election",
		Status: "pending",
	}
	electionJSON, _ := json.Marshal(election)
	stub.State["election:election-001"] = electionJSON

	// Activate
	err := contract.ActivateElection(ctx, "election-001")
	assert.NoError(t, err)

	// Verify status changed
	stored := stub.State["election:election-001"]
	var updated Election
	_ = json.Unmarshal(stored, &updated)
	assert.Equal(t, "active", updated.Status)
}

func TestCastVote(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Setup active election
	election := createMockElection()
	electionJSON, _ := json.Marshal(election)
	stub.State["election:election-001"] = electionJSON

	// Initialize vote index
	stub.State["voteindex:election-001"] = []byte("[]")

	// Cast vote
	receipt, err := contract.CastVote(
		ctx,
		"election-001",
		`{"ciphertext":"encrypted"}`,
		"nullifier123",
		"eligibilityproof",
		"validityproof",
	)

	assert.NoError(t, err)
	assert.NotNil(t, receipt)
	assert.True(t, receipt.Success)
	assert.NotEmpty(t, receipt.VerificationCode)
	assert.NotEmpty(t, receipt.TxID)
}

func TestCastVoteDuplicateNullifier(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Setup active election
	election := createMockElection()
	electionJSON, _ := json.Marshal(election)
	stub.State["election:election-001"] = electionJSON
	stub.State["voteindex:election-001"] = []byte("[]")

	// First vote
	_, _ = contract.CastVote(ctx, "election-001", "{}", "nullifier123", "proof1", "proof2")

	// Second vote with same nullifier
	_, err := contract.CastVote(ctx, "election-001", "{}", "nullifier123", "proof1", "proof2")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "duplicate")
}

func TestCastVoteInactiveElection(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Setup inactive election
	election := &Election{
		ID:     "election-001",
		Status: "closed",
	}
	electionJSON, _ := json.Marshal(election)
	stub.State["election:election-001"] = electionJSON

	// Try to cast vote
	_, err := contract.CastVote(ctx, "election-001", "{}", "nullifier", "proof1", "proof2")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not active")
}

func TestGetVote(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Store a vote
	vote := &Vote{
		ElectionID:        "election-001",
		EncryptedVote:     "encrypted_data",
		EncryptedVoteHash: "hash123",
		Nullifier:         "nullifier123",
		TxID:              "tx123",
	}
	voteJSON, _ := json.Marshal(vote)
	stub.State["vote:election-001:nullifier123"] = voteJSON

	// Get vote
	retrieved, err := contract.GetVote(ctx, "election-001", "nullifier123")
	assert.NoError(t, err)
	assert.Equal(t, "hash123", retrieved.EncryptedVoteHash)
}

func TestGetVoteNotFound(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	_, err := contract.GetVote(ctx, "election-001", "nonexistent")
	assert.Error(t, err)
	assert.Contains(t, err.Error(), "not found")
}

func TestVerifyVote(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Store a vote
	vote := &Vote{
		ElectionID:        "election-001",
		EncryptedVoteHash: "correcthash",
		Nullifier:         "nullifier123",
		TxID:              "tx123",
	}
	voteJSON, _ := json.Marshal(vote)
	stub.State["vote:election-001:nullifier123"] = voteJSON

	// Verify with correct hash
	result, err := contract.VerifyVote(ctx, "election-001", "nullifier123", "correcthash")
	assert.NoError(t, err)
	assert.True(t, result["verified"].(bool))

	// Verify with incorrect hash
	result, err = contract.VerifyVote(ctx, "election-001", "nullifier123", "wronghash")
	assert.NoError(t, err)
	assert.False(t, result["verified"].(bool))
}

func TestStoreTallyResult(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Setup closed election
	election := &Election{
		ID:     "election-001",
		Status: "closed",
	}
	electionJSON, _ := json.Marshal(election)
	stub.State["election:election-001"] = electionJSON
	stub.State["bulletinboard:election-001"] = []byte("[]")

	// Store tally
	voteCounts := `{"1": 100, "2": 75, "3": 50}`
	err := contract.StoreTallyResult(
		ctx,
		"election-001",
		voteCounts,
		"aggregatedhash",
		"decryptionproof",
	)

	assert.NoError(t, err)

	// Verify tally was stored
	stored := stub.State["tally:election-001"]
	assert.NotNil(t, stored)

	var result TallyResult
	_ = json.Unmarshal(stored, &result)
	assert.Equal(t, 225, result.TotalVotes)
}

func TestGetTallyResult(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Store tally result
	result := &TallyResult{
		ElectionID:      "election-001",
		VoteCounts:      map[string]int{"1": 100, "2": 50},
		TotalVotes:      150,
		AggregatedHash:  "hash",
		DecryptionProof: "proof",
	}
	resultJSON, _ := json.Marshal(result)
	stub.State["tally:election-001"] = resultJSON

	// Get tally
	retrieved, err := contract.GetTallyResult(ctx, "election-001")
	assert.NoError(t, err)
	assert.Equal(t, 150, retrieved.TotalVotes)
	assert.Equal(t, 100, retrieved.VoteCounts["1"])
}

func TestGetBulletinBoard(t *testing.T) {
	contract := new(VoteContract)
	ctx := new(MockTransactionContext)
	stub := NewMockStub()

	ctx.On("GetStub").Return(stub)

	// Store bulletin board entries
	entries := []BulletinBoardEntry{
		{Sequence: 1, Type: "election_created", Hash: "hash1", TxID: "tx1"},
		{Sequence: 2, Type: "vote_cast", Hash: "hash2", TxID: "tx2"},
	}
	entriesJSON, _ := json.Marshal(entries)
	stub.State["bulletinboard:election-001"] = entriesJSON

	// Get bulletin board
	result, err := contract.GetBulletinBoard(ctx, "election-001")
	assert.NoError(t, err)
	assert.NotNil(t, result["entries"])
	assert.NotEmpty(t, result["merkleRoot"])
}

func TestComputeMerkleRoot(t *testing.T) {
	entries := []BulletinBoardEntry{
		{Sequence: 1, Type: "test1", Hash: "hash1", TxID: "tx1"},
		{Sequence: 2, Type: "test2", Hash: "hash2", TxID: "tx2"},
		{Sequence: 3, Type: "test3", Hash: "hash3", TxID: "tx3"},
	}

	root := computeMerkleRoot(entries)
	assert.NotEmpty(t, root)
	assert.Len(t, root, 64) // SHA256 hex

	// Same entries should give same root
	root2 := computeMerkleRoot(entries)
	assert.Equal(t, root, root2)
}

func TestHashString(t *testing.T) {
	hash1 := hashString("test")
	hash2 := hashString("test")
	hash3 := hashString("different")

	assert.Equal(t, hash1, hash2)
	assert.NotEqual(t, hash1, hash3)
	assert.Len(t, hash1, 64)
}

func TestGenerateVerificationCode(t *testing.T) {
	code1 := generateVerificationCode("tx1", "hash1")
	code2 := generateVerificationCode("tx1", "hash1")
	code3 := generateVerificationCode("tx2", "hash2")

	assert.Equal(t, code1, code2)
	assert.NotEqual(t, code1, code3)
	assert.Len(t, code1, 16)
}
