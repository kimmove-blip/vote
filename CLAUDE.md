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
source venv/bin/activate
pip install -r requirements.txt

# Run server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest tests/ -v
pytest tests/ -v --cov=app  # with coverage

# Run single test file
pytest tests/test_vote.py -v
```

### Mobile (React Native)
```bash
cd mobile
npm install

npm run ios          # iOS
npm run android      # Android
npm test             # Jest tests
npm run lint         # ESLint
npm run type-check   # TypeScript check
```

### Blockchain Chaincode (Go)
```bash
cd blockchain/chaincode/vote
go test ./...        # Run chaincode tests
```

### ZKP Circuits (Zokrates)
```bash
# Install: curl -LSfs get.zokrat.es | sh
cd zkp-circuits/eligibility
zokrates compile -i eligibility.zok
zokrates setup
```

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

```
POST /api/v1/auth/did/verify      - Verify DID
POST /api/v1/auth/fido/register   - Register FIDO credential
GET  /api/v1/elections            - List elections
POST /api/v1/elections            - Create election (admin)
POST /api/v1/votes/token          - Request vote token
POST /api/v1/votes/submit         - Submit encrypted vote
GET  /api/v1/votes/receipt/{code} - Get vote receipt
POST /api/v1/tally/start          - Start tallying (admin)
GET  /api/v1/verification/cast/{code} - Verify vote
GET  /health                      - Health check
```

## Configuration

Environment variables in `backend/app/core/config.py`:
- `DATABASE_URL` - SQLite (dev) or PostgreSQL (prod)
- `REDIS_URL` - Cache
- `JWT_SECRET_KEY`, `JWT_ALGORITHM=RS256`
- `FABRIC_*` - Hyperledger Fabric settings
- `ELECTION_KEY_THRESHOLD=3`, `ELECTION_KEY_TOTAL_SHARES=5` - Threshold decryption

## Infrastructure

Production deployment uses AWS:
- EKS (Kubernetes) with separate node groups for app and blockchain
- RDS PostgreSQL (Multi-AZ)
- ElastiCache Redis
- CloudFront + WAF + Shield Advanced
- Terraform configs in `infrastructure/terraform/`

## Language

- Code and technical docs: English
- UI and user-facing docs: Korean (한국어)
