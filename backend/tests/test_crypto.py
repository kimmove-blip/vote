"""
Tests for cryptographic modules.
"""
import pytest
import json

from app.crypto.homomorphic.cgs_protocol import CGSProtocol, encrypt_vote
from app.crypto.zkp.zokrates_engine import (
    ZokratesEngine,
    MerkleTree,
    create_voter_commitment,
    compute_nullifier,
)


class TestCGSProtocol:
    """Test cases for CGS homomorphic encryption."""

    def test_keypair_generation(self):
        """Test key pair generation."""
        cgs = CGSProtocol()
        public_key, private_key = cgs.generate_keypair()

        assert public_key.p > 0
        assert public_key.q > 0
        assert public_key.g > 0
        assert public_key.h > 0
        assert private_key.x > 0

    def test_encrypt_decrypt(self):
        """Test encryption and decryption."""
        cgs = CGSProtocol()
        public_key, private_key = cgs.generate_keypair()

        # Encrypt message
        message = 1
        ciphertext = cgs.encrypt(public_key, message)

        # Decrypt
        decrypted = cgs.decrypt(ciphertext, private_key, public_key)

        assert decrypted == message

    def test_encrypt_zero(self):
        """Test encrypting zero."""
        cgs = CGSProtocol()
        public_key, private_key = cgs.generate_keypair()

        ciphertext = cgs.encrypt(public_key, 0)
        decrypted = cgs.decrypt(ciphertext, private_key, public_key)

        assert decrypted == 0

    def test_homomorphic_addition(self):
        """Test homomorphic addition property."""
        cgs = CGSProtocol()
        public_key, private_key = cgs.generate_keypair()

        # Encrypt two values
        m1, m2 = 3, 5
        c1 = cgs.encrypt(public_key, m1)
        c2 = cgs.encrypt(public_key, m2)

        # Serialize and add homomorphically
        c1_str = cgs._serialize_ciphertext(c1)
        c2_str = cgs._serialize_ciphertext(c2)
        sum_str = cgs.homomorphic_add(c1_str, c2_str)

        # Decrypt sum
        sum_ct = cgs._deserialize_ciphertext(sum_str)
        decrypted_sum = cgs.decrypt(sum_ct, private_key, public_key)

        assert decrypted_sum == m1 + m2

    def test_threshold_key_generation(self):
        """Test threshold key generation."""
        cgs = CGSProtocol()
        threshold = 3
        total_shares = 5

        public_key, shares = cgs.generate_threshold_keys(threshold, total_shares)

        assert len(shares) == total_shares
        for share in shares:
            assert share.index > 0
            assert share.share > 0
            assert share.verification_point > 0

    def test_threshold_decryption(self):
        """Test threshold decryption."""
        cgs = CGSProtocol()
        threshold = 3
        total_shares = 5

        public_key, shares = cgs.generate_threshold_keys(threshold, total_shares)

        # Encrypt a message
        message = 7
        ciphertext = cgs.encrypt(public_key, message)

        # Use only threshold number of shares
        selected_shares = shares[:threshold]

        # Decrypt with threshold shares
        decrypted = cgs.threshold_decrypt(ciphertext, selected_shares, public_key)

        assert decrypted == message

    def test_key_share_proof_verification(self):
        """Test key share proof verification."""
        cgs = CGSProtocol()
        public_key, shares = cgs.generate_threshold_keys(3, 5)

        # Serialize and verify a share
        share = shares[0]
        share_str = cgs._serialize_key_share(share)

        # Generate proof (for testing, the share itself serves as proof)
        proof = json.dumps({"verification_point": str(share.verification_point)})

        is_valid = cgs.verify_key_share_proof(share_str, proof)
        assert is_valid

    def test_public_key_serialization(self):
        """Test public key serialization and deserialization."""
        cgs = CGSProtocol()
        public_key, _ = cgs.generate_keypair()

        serialized = cgs.serialize_public_key(public_key)
        deserialized = cgs.deserialize_public_key(serialized)

        assert deserialized.p == public_key.p
        assert deserialized.q == public_key.q
        assert deserialized.g == public_key.g
        assert deserialized.h == public_key.h


class TestMerkleTree:
    """Test cases for Merkle tree implementation."""

    def test_empty_tree(self):
        """Test empty tree root."""
        tree = MerkleTree(depth=4)
        root = tree.get_root()

        assert root is not None
        assert len(root) == 64  # SHA256 hex

    def test_add_leaf(self):
        """Test adding leaves."""
        tree = MerkleTree(depth=4)

        index1 = tree.add_leaf("commitment1")
        index2 = tree.add_leaf("commitment2")

        assert index1 == 0
        assert index2 == 1

    def test_merkle_proof(self):
        """Test Merkle proof generation and verification."""
        tree = MerkleTree(depth=4)

        # Add some leaves
        tree.add_leaf("leaf1")
        tree.add_leaf("leaf2")
        tree.add_leaf("leaf3")

        root = tree.get_root()

        # Get proof for leaf1
        path, indices = tree.get_proof(0)

        # Verify proof
        is_valid = tree.verify_proof("leaf1", path, indices, root)
        assert is_valid

    def test_invalid_merkle_proof(self):
        """Test that invalid proofs fail."""
        tree = MerkleTree(depth=4)

        tree.add_leaf("leaf1")
        tree.add_leaf("leaf2")

        root = tree.get_root()
        path, indices = tree.get_proof(0)

        # Try to verify wrong leaf
        is_valid = tree.verify_proof("wrong_leaf", path, indices, root)
        assert not is_valid

    def test_tree_capacity(self):
        """Test tree capacity enforcement."""
        tree = MerkleTree(depth=2)  # Can hold 4 leaves

        for i in range(4):
            tree.add_leaf(f"leaf{i}")

        # Adding 5th leaf should fail
        with pytest.raises(ValueError):
            tree.add_leaf("overflow")


class TestVoterCommitment:
    """Test cases for voter commitment functions."""

    def test_create_commitment(self):
        """Test voter commitment creation."""
        commitment = create_voter_commitment("voter123", "secret456")

        assert commitment is not None
        assert len(commitment) == 64  # SHA256 hex

    def test_commitment_deterministic(self):
        """Test that commitment is deterministic."""
        c1 = create_voter_commitment("voter", "secret")
        c2 = create_voter_commitment("voter", "secret")

        assert c1 == c2

    def test_commitment_uniqueness(self):
        """Test that different inputs give different commitments."""
        c1 = create_voter_commitment("voter1", "secret")
        c2 = create_voter_commitment("voter2", "secret")

        assert c1 != c2


class TestNullifier:
    """Test cases for nullifier computation."""

    def test_compute_nullifier(self):
        """Test nullifier computation."""
        nullifier = compute_nullifier("secret", "election123")

        assert nullifier is not None
        assert len(nullifier) == 64  # SHA256 hex

    def test_nullifier_deterministic(self):
        """Test that nullifier is deterministic."""
        n1 = compute_nullifier("secret", "election")
        n2 = compute_nullifier("secret", "election")

        assert n1 == n2

    def test_nullifier_election_specific(self):
        """Test that nullifiers are election-specific."""
        n1 = compute_nullifier("secret", "election1")
        n2 = compute_nullifier("secret", "election2")

        assert n1 != n2


class TestZokratesEngine:
    """Test cases for ZKP engine."""

    @pytest.mark.asyncio
    async def test_verify_eligibility_proof_structure(self):
        """Test eligibility proof verification with valid structure."""
        engine = ZokratesEngine()

        # Create a properly structured proof
        import secrets
        proof = json.dumps({
            "a": [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
            "b": [
                [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
                [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
            ],
            "c": [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
        })

        merkle_root = "0x" + "a" * 64
        nullifier = "0x" + "b" * 64

        # Should verify structure (dev mode)
        is_valid = await engine.verify_eligibility_proof(proof, merkle_root, nullifier)
        assert is_valid

    @pytest.mark.asyncio
    async def test_verify_validity_proof_structure(self):
        """Test validity proof verification with valid structure."""
        engine = ZokratesEngine()

        import secrets
        proof = json.dumps({
            "a": [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
            "b": [
                [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
                [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
            ],
            "c": [hex(secrets.randbits(256)), hex(secrets.randbits(256))],
        })

        encrypted_vote = '{"ciphertexts": []}'
        public_key = '{"p": "123", "g": "2", "h": "456"}'

        is_valid = await engine.verify_validity_proof(proof, encrypted_vote, public_key)
        assert is_valid

    @pytest.mark.asyncio
    async def test_invalid_proof_structure(self):
        """Test that invalid proof structures fail."""
        engine = ZokratesEngine()

        invalid_proof = '{"invalid": "structure"}'
        merkle_root = "0x" + "a" * 64
        nullifier = "0x" + "b" * 64

        is_valid = await engine.verify_eligibility_proof(invalid_proof, merkle_root, nullifier)
        assert not is_valid
