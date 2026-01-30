# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A blockchain-based mobile voting system combining:
- **Hyperledger Fabric** - Immutable vote records
- **CGS Homomorphic Encryption** - Privacy-preserving vote tallying without decrypting individual votes
- **Zokrates ZKP** - Voter eligibility verification without revealing identity
- **DID + FIDO2** - Decentralized authentication with biometrics

## Common Commands

### Backend (FastAPI/Python)
```bash
cd backend

# Setup (first time)
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
pytest tests/ -v --cov=app  # with coverage

# Run single test file
pytest tests/test_votes.py -v
pytest tests/test_elections.py -v
pytest tests/test_crypto.py -v

# Database (SQLite in development, no migrations needed)
# For production PostgreSQL migrations, set DATABASE_URL env var
```

### Mobile (React Native)
```bash
cd mobile
npm install

# iOS (requires macOS)
npx pod-install      # Install iOS dependencies
npm run ios

# Android
npm run android

# Testing and code quality
npm test             # Jest tests
npm run lint         # ESLint
npm run type-check   # TypeScript check
```

### Blockchain Chaincode (Go)
```bash
cd blockchain/chaincode/vote

# Run chaincode tests
go test ./...
go test -v ./contracts  # Verbose test output

# The chaincode is deployed to Hyperledger Fabric network
# See blockchain/network/ for network setup scripts
```

### ZKP Circuits (Zokrates)
```bash
# Install Zokrates
curl -LSfs get.zokrat.es | sh
export PATH=$HOME/.zokrates/bin:$PATH

# Compile and setup eligibility circuit (voter in Merkle tree)
cd zkp-circuits/eligibility
zokrates compile -i eligibility.zok
zokrates setup                    # Generates proving.key and verification.key

# Compile and setup validity circuit (vote is valid)
cd ../validity
zokrates compile -i validity.zok
zokrates setup

# Generate proof (example)
zokrates compute-witness -a <public_inputs> <private_inputs>
zokrates generate-proof
```

See `zkp-circuits/README.md` for detailed circuit documentation.

## Architecture

### Three Voting Modes

The system implements three distinct voting modes configured per election:

1. **SINGLE** - Traditional 1 person = 1 vote
2. **MULTI_LIMITED** - Multiple candidates with configurable limits (`max_candidates_per_voter`, `max_votes_per_candidate`)
3. **PERIODIC_RESET** - Voting rights reset at intervals (`reset_interval_hours`), previous votes remain counted

### Cryptographic Flow
```
Voter Registration → Merkle Tree (voter list) → ZKP Circuit Compilation
                                                          ↓
                              Vote Submission ←── Election Init (threshold keys)
                                    ↓
                    1. DID proof (eligibility)
                    2. CGS encrypt vote
                    3. ZKP generate (validity)
                    4. Submit to blockchain
                                    ↓
                              Tally (off-chain)
                    1. Homomorphic aggregation
                    2. Threshold decryption (3-of-5)
                    3. Publish results
```

### Key Service Layers

| Layer | Location | Purpose |
|-------|----------|---------|
| API Endpoints | `backend/app/api/v1/endpoints/` | REST handlers |
| Business Logic | `backend/app/services/` | Vote submission, tallying, verification |
| Cryptography | `backend/app/crypto/homomorphic/cgs_protocol.py` | CGS encryption |
| ZKP Engine | `backend/app/crypto/zkp/zokrates_engine.py` | Proof generation/verification |
| Fabric Client | `backend/app/fabric/fabric_client.py` | Blockchain integration |
| Models | `backend/app/models/` | SQLAlchemy ORM (election.py, vote.py, user.py) |

### Database

- **Development**: SQLite with aiosqlite
- **Production**: PostgreSQL with asyncpg

Key tables: `elections`, `candidates`, `vote_tokens`, `vote_receipts`, `voter_participations`, `vote_audit_logs`

### Double-Voting Prevention

- Vote tokens (one-time, hashed storage)
- Nullifier hashes on blockchain
- `VoterParticipation` tracking per voting period

### Verification Types

1. **Cast-as-intended** - Verify encrypted vote matches choice
2. **Recorded-as-cast** - Verify vote recorded on blockchain
3. **Tallied-as-recorded** - Verify tally includes all votes

## API Endpoints

Backend API endpoints are organized in `backend/app/api/v1/endpoints/`:

| Module | Key Endpoints |
|--------|---------------|
| **auth.py** | `POST /api/v1/auth/did/verify` - DID authentication<br>`POST /api/v1/auth/fido/register` - FIDO2 registration |
| **elections.py** | `GET /api/v1/elections` - List elections<br>`POST /api/v1/elections` - Create election (admin)<br>`GET /api/v1/elections/{id}` - Election details |
| **votes.py** | `POST /api/v1/votes/token` - Request vote token<br>`POST /api/v1/votes/submit` - Submit encrypted vote<br>`GET /api/v1/votes/receipt/{code}` - Get receipt |
| **tally.py** | `POST /api/v1/tally/start` - Start tallying (admin)<br>`GET /api/v1/tally/{election_id}` - Get results |
| **verification.py** | `GET /api/v1/verification/cast/{code}` - Verify cast-as-intended<br>`GET /api/v1/verification/recorded/{code}` - Verify recorded-as-cast |

Health check: `GET /health`

## Configuration

Environment variables in `backend/app/core/config.py`:

**Database & Cache:**
- `DATABASE_URL` - SQLite (dev): `sqlite+aiosqlite:///./vote.db`, PostgreSQL (prod)
- `REDIS_URL` - Cache and session storage

**Authentication:**
- `JWT_SECRET_KEY`, `JWT_ALGORITHM=RS256`
- `FIDO2_RP_ID`, `FIDO2_RP_NAME`, `FIDO2_ORIGIN` - FIDO2 relying party config
- `DID_RESOLVER_URL`, `OMNIONE_API_URL`, `OMNIONE_API_KEY` - DID authentication

**Blockchain:**
- `FABRIC_NETWORK_CONFIG` - Path to Hyperledger Fabric network config
- `FABRIC_CHANNEL_NAME=votingchannel`, `FABRIC_CHAINCODE_NAME=votecontract`
- `FABRIC_ORG_NAME=NEC`, `FABRIC_PEER_ENDPOINT` - Organization settings

**Cryptography:**
- `ELECTION_KEY_THRESHOLD=3`, `ELECTION_KEY_TOTAL_SHARES=5` - Threshold decryption (3-of-5)
- `ZKP_PROVING_KEY_PATH`, `ZKP_VERIFICATION_KEY_PATH` - ZKP key locations

**AWS (Production):**
- `AWS_REGION=ap-northeast-2`, `AWS_KMS_KEY_ID`, `AWS_SQS_QUEUE_URL`

**Security:**
- `CORS_ORIGINS` - Allowed origins (includes localhost for dev)
- `RATE_LIMIT_REQUESTS=100`, `RATE_LIMIT_WINDOW_SECONDS=60`

## Infrastructure

Production deployment uses AWS:
- EKS (Kubernetes) with separate node groups for app and blockchain
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis
- CloudFront + WAF + Shield Advanced
- Terraform configs in `infrastructure/terraform/`

## Development Workflow

### Local Development Stack

1. **Backend**: FastAPI server on port 8000 (SQLite database)
2. **Mobile**: React Native app via Metro bundler
3. **Web**: Serve `web/index.html` via `python -m http.server 8080` or open directly

### Testing Strategy

- **Backend**: `pytest` for unit/integration tests in `backend/tests/`
- **Chaincode**: `go test` for smart contract logic
- **Mobile**: Jest for React Native components
- **Cryptography**: Dedicated tests in `backend/tests/test_crypto.py`

### Common Development Tasks

**Add a new API endpoint:**
1. Create handler in `backend/app/api/v1/endpoints/`
2. Add route to `backend/app/api/v1/router.py`
3. Create Pydantic schemas in `backend/app/schemas/`
4. Implement business logic in `backend/app/services/`

**Add a new election mode:**
1. Update `VotingMode` enum in `backend/app/models/election.py`
2. Add validation logic in `backend/app/services/vote_service.py`
3. Update mobile UI in `mobile/src/screens/`

**Modify cryptographic protocol:**
1. Update `backend/app/crypto/homomorphic/cgs_protocol.py` or ZKP circuits
2. Regenerate ZKP keys if circuits changed
3. Update corresponding tests

## Web Interfaces

The `web/` directory contains static HTML/Vue.js applications:
- **index.html** - Admin portal for election management (Vue 3 + Tailwind CSS)
- **voter.html** - Voter verification portal for checking vote receipts

Both are single-file applications using CDN-loaded libraries. No build step required.

## Important Notes

### Hybrid Architecture (On-chain vs Off-chain)

The system uses a **hybrid approach** to balance security and scalability:

- **On-chain (Hyperledger Fabric)**: Vote records, nullifiers, audit trail
- **Off-chain (Backend)**: ZKP generation, CGS encryption/decryption, complex computations

This prevents blockchain network congestion while maintaining immutability for critical data.

### Security Model

1. **Vote Privacy**: CGS homomorphic encryption allows tallying without decrypting individual votes
2. **Voter Anonymity**: ZKP proves eligibility without revealing identity
3. **Double-Vote Prevention**:
   - Vote tokens (one-time use, hashed)
   - Nullifier hashes on blockchain
   - `VoterParticipation` DB tracking per period
4. **Threshold Decryption**: Requires 3 of 5 key holders to decrypt results (no single point of failure)

### Testing Important Cryptographic Features

When testing vote submission and tallying:
- Ensure encrypted votes can be aggregated homomorphically
- Verify ZKP proofs are valid without revealing private inputs
- Test that nullifiers prevent double-voting
- Confirm threshold decryption requires minimum shares

## Language

- Code and technical docs: English
- UI and user-facing docs: Korean (한국어)
