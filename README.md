# Global Mobile Blockchain Voting System

A secure, transparent, and verifiable electronic voting system using blockchain technology, homomorphic encryption, and zero-knowledge proofs.

## Overview

This system combines cutting-edge cryptographic techniques to provide a mathematically secure voting platform:

- **Blockchain (Hyperledger Fabric)**: Immutable record of all votes
- **Homomorphic Encryption (CGS)**: Privacy-preserving vote tallying
- **Zero-Knowledge Proofs (Zokrates)**: Verify eligibility without revealing identity
- **DID + FIDO2**: Strong, decentralized authentication

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Client Layer                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ React Native │  │  Admin Web   │  │  Verifier    │          │
│  │  Mobile App  │  │   Portal     │  │    Web       │          │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘          │
└─────────┼─────────────────┼─────────────────┼───────────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────┐
│                     AWS Edge Layer                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ CloudFront  │──│    WAF      │──│   Shield    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Application Layer                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   FastAPI Backend                        │   │
│  │  ┌────────────┐  ┌────────────┐  ┌────────────┐        │   │
│  │  │   Auth     │  │   Vote     │  │   Tally    │        │   │
│  │  │  Service   │  │  Service   │  │  Service   │        │   │
│  │  └────────────┘  └────────────┘  └────────────┘        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Blockchain Layer                               │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Hyperledger Fabric Network                  │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │   │
│  │  │   NEC    │  │   MOIS   │  │   BAI    │  (Organizations)│ │
│  │  │  Peers   │  │  Peers   │  │  Peers   │              │   │
│  │  └──────────┘  └──────────┘  └──────────┘              │   │
│  │         Raft Orderer Cluster (5 nodes)                  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
/home/kimhc/vote/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/v1/endpoints/  # API endpoints
│   │   ├── core/              # Configuration
│   │   ├── models/            # Database models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   ├── crypto/            # Cryptographic modules
│   │   │   ├── homomorphic/   # CGS encryption
│   │   │   └── zkp/           # ZKP engine
│   │   └── fabric/            # Fabric SDK
│   └── tests/                 # Backend tests
│
├── mobile/                    # React Native app
│   └── src/
│       ├── screens/           # UI screens
│       ├── services/          # API & crypto
│       └── store/             # Redux state
│
├── blockchain/                # Hyperledger Fabric
│   ├── network/               # Network config
│   └── chaincode/vote/        # Vote chaincode
│
├── zkp-circuits/              # Zokrates circuits
│   ├── eligibility/           # Eligibility proof
│   └── validity/              # Vote validity proof
│
└── infrastructure/            # IaC
    ├── terraform/             # AWS infrastructure
    └── kubernetes/            # K8s deployments
```

## Key Features

### Security

- **End-to-end verifiability**: Voters can verify their vote was recorded correctly
- **Voter anonymity**: Zero-knowledge proofs hide voter identity
- **Double-voting prevention**: Cryptographic nullifiers prevent multiple votes
- **Threshold decryption**: 3-of-5 key holders required to decrypt results
- **Immutable audit trail**: All actions recorded on blockchain

### Verification Types

1. **Cast-as-intended**: Verify encrypted vote matches your choice
2. **Recorded-as-cast**: Verify vote recorded on blockchain
3. **Tallied-as-recorded**: Verify tally includes all votes

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Go 1.21+
- Docker & Docker Compose
- AWS CLI (for deployment)

### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/ -v

# Start development server
uvicorn app.main:app --reload --port 8000
```

### Mobile Development

```bash
cd mobile

# Install dependencies
npm install

# iOS
npx pod-install
npm run ios

# Android
npm run android
```

### Blockchain Network

```bash
cd blockchain/network

# Generate crypto materials
./generate.sh

# Start network
docker-compose up -d

# Deploy chaincode
./deploy-chaincode.sh
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/did/verify` | Verify DID presentation |
| POST | `/api/v1/auth/fido/register` | Register FIDO credential |
| GET | `/api/v1/elections` | List elections |
| GET | `/api/v1/elections/{id}` | Get election details |
| POST | `/api/v1/votes/token` | Request vote token |
| POST | `/api/v1/votes/submit` | Submit encrypted vote |
| GET | `/api/v1/votes/receipt/{code}` | Get vote receipt |
| POST | `/api/v1/tally/start` | Start tally process |
| GET | `/api/v1/verification/cast/{code}` | Verify vote |

## Cryptographic Protocols

### CGS Homomorphic Encryption

The system uses a variant of Cramer-Gennaro-Schoenmakers protocol:

```
Encryption: E(m) = (g^r, h^r * g^m)
Homomorphic addition: E(m1) * E(m2) = E(m1 + m2)
Threshold decryption: Requires k-of-n key shares
```

### Zero-Knowledge Proofs

Two ZKP circuits are used:

1. **Eligibility Proof**: Proves Merkle tree membership without revealing identity
2. **Validity Proof**: Proves vote is for valid candidate without revealing choice

## Testing

```bash
# Backend tests
cd backend && pytest tests/ -v --cov=app

# Chaincode tests
cd blockchain/chaincode/vote && go test ./...

# Mobile tests
cd mobile && npm test

# E2E tests
./scripts/e2e-test.sh
```

## Deployment

### Infrastructure

```bash
cd infrastructure/terraform

# Initialize
terraform init

# Plan
terraform plan -var-file=production.tfvars

# Apply
terraform apply -var-file=production.tfvars
```

### Kubernetes

```bash
cd infrastructure/kubernetes

# Apply configurations
kubectl apply -f deployment.yaml
```

## Security Considerations

1. **Key Management**: Use AWS KMS for encryption keys
2. **Audit Logging**: All actions logged to immutable store
3. **Rate Limiting**: Protect against DoS attacks
4. **Input Validation**: Strict validation on all inputs
5. **Network Isolation**: VPC with private subnets

## Compliance

- WCAG 2.1 accessibility guidelines
- GDPR data protection requirements
- Election commission security standards

## Contributing

1. Fork the repository
2. Create a feature branch
3. Write tests for new features
4. Submit a pull request

## License

Copyright 2024. All rights reserved.

## Contact

For questions or support, contact the development team.
