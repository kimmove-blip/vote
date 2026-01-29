# ZKP Circuits for Blockchain Voting System

This directory contains Zokrates zero-knowledge proof circuits used in the voting system.

## Circuits

### 1. Eligibility Circuit (`eligibility/eligibility.zok`)

Proves that a voter is eligible to vote without revealing their identity.

**Public Inputs:**
- `merkleRoot`: The Merkle root of the eligible voter tree
- `nullifier`: Unique identifier to prevent double voting
- `electionId`: Election identifier

**Private Inputs:**
- `voterSecret`: The voter's secret key
- `merklePath`: The sibling hashes along the Merkle path
- `pathIndices`: Direction indicators at each tree level
- `treeDepth`: Depth of the Merkle tree

**What it proves:**
1. The voter's commitment exists in the eligible voter Merkle tree
2. The nullifier is correctly computed from the voter's secret and election ID
3. The voter knows the secret corresponding to their commitment

### 2. Validity Circuit (`validity/validity.zok`)

Proves that an encrypted vote is valid without revealing the choice.

**Public Inputs:**
- `encryptedVoteCommitment`: Hash of the encrypted vote
- `publicKeyHash`: Hash of the election public key
- `numCandidates`: Number of valid candidates

**Private Inputs:**
- `voteChoice`: The actual vote choice
- `encryptionRandomness`: Randomness used in CGS encryption

**What it proves:**
1. The vote is for exactly one candidate (unit vector property)
2. The vote choice is within the valid range
3. The encryption was performed correctly

## Building the Circuits

### Prerequisites

1. Install Zokrates:
```bash
curl -LSfs get.zokrat.es | sh
```

2. Add Zokrates to PATH:
```bash
export PATH=$HOME/.zokrates/bin:$PATH
```

### Compile Circuits

```bash
# Compile eligibility circuit
cd eligibility
zokrates compile -i eligibility.zok

# Compile validity circuit
cd ../validity
zokrates compile -i validity.zok
```

### Generate Keys

```bash
# Generate proving and verification keys for eligibility
cd eligibility
zokrates setup

# Generate keys for validity
cd ../validity
zokrates setup
```

### Generate Proofs (Example)

```bash
# Compute witness for eligibility
zokrates compute-witness -a <merkleRoot0> <merkleRoot1> <nullifier0> <nullifier1> ...

# Generate proof
zokrates generate-proof

# Export verifier (for on-chain verification)
zokrates export-verifier
```

## Integration

### Backend Integration

The backend uses the `zokrates_engine.py` module to:
1. Generate proofs when voters submit their votes
2. Verify proofs before recording votes on the blockchain

### Client Integration

The mobile app uses the `encryption.ts` module to:
1. Prepare proof inputs
2. Call the backend proof generation API
3. Submit proofs with encrypted votes

## Security Considerations

1. **Trusted Setup**: The circuits use Groth16 which requires a trusted setup.
   In production, use a multi-party computation (MPC) ceremony.

2. **Randomness**: Ensure cryptographically secure randomness for:
   - Voter secrets
   - Encryption randomness
   - Challenge generation

3. **Side Channels**: Protect proof generation from timing attacks.

4. **Key Management**: Securely store and manage proving keys.

## Circuit Parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| Tree Depth | 20 | Supports ~1 million voters |
| Max Candidates | 20 | Maximum candidates per election |
| Hash Function | SHA256 | Poseidon recommended for production |

## Testing

```bash
# Run circuit tests
cd tests
./run_tests.sh
```

## References

- [Zokrates Documentation](https://zokrates.github.io/)
- [Groth16 Paper](https://eprint.iacr.org/2016/260)
- [CGS Voting Protocol](https://www.usenix.org/legacy/event/sec97/full_papers/cramer/cramer.pdf)
