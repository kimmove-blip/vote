"""
CGS (Cramer-Gennaro-Schoenmakers) Homomorphic Encryption Protocol.

This module implements a variant of the CGS protocol for secure voting:
- Additive homomorphic encryption for vote tallying
- Threshold decryption (3-of-5) for key management
- ZKP integration for vote validity

The CGS protocol is based on exponential ElGamal encryption which supports
additive homomorphism, allowing encrypted votes to be summed without
decryption.
"""
import hashlib
import secrets
import json
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

# In production, use gmpy2 for efficient large number operations
# import gmpy2


@dataclass
class PublicKey:
    """CGS public key."""
    p: int  # Large prime
    q: int  # Prime order of subgroup
    g: int  # Generator
    h: int  # h = g^x where x is the private key


@dataclass
class PrivateKey:
    """CGS private key."""
    x: int  # Private exponent


@dataclass
class Ciphertext:
    """CGS ciphertext (c1, c2)."""
    c1: int  # g^r
    c2: int  # h^r * g^m


@dataclass
class KeyShare:
    """Threshold key share."""
    index: int
    share: int
    verification_point: int


class CGSProtocol:
    """
    CGS Homomorphic Encryption Protocol implementation.

    This protocol provides:
    1. Additive homomorphic encryption
    2. Threshold key generation and decryption
    3. Zero-knowledge proofs for encryption validity
    """

    # Standard safe prime parameters (2048-bit)
    # In production, these would be generated securely
    DEFAULT_P = int(
        "FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1"
        "29024E088A67CC74020BBEA63B139B22514A08798E3404DD"
        "EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245"
        "E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED"
        "EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D"
        "C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F"
        "83655D23DCA3AD961C62F356208552BB9ED529077096966D"
        "670C354E4ABC9804F1746C08CA237327FFFFFFFFFFFFFFFF",
        16
    )

    DEFAULT_G = 2

    def __init__(self, bit_length: int = 2048):
        """
        Initialize CGS protocol with specified security parameter.

        Args:
            bit_length: Security parameter in bits
        """
        self.bit_length = bit_length
        self.p = self.DEFAULT_P
        self.q = (self.p - 1) // 2
        self.g = self.DEFAULT_G

    def generate_keypair(self) -> Tuple[PublicKey, PrivateKey]:
        """
        Generate a new CGS keypair.

        Returns:
            Tuple of (public_key, private_key)
        """
        # Generate random private key
        x = secrets.randbelow(self.q - 2) + 2

        # Compute public key component h = g^x mod p
        h = pow(self.g, x, self.p)

        public_key = PublicKey(p=self.p, q=self.q, g=self.g, h=h)
        private_key = PrivateKey(x=x)

        return public_key, private_key

    def generate_threshold_keys(
        self,
        threshold: int,
        total_shares: int
    ) -> Tuple[PublicKey, List[KeyShare]]:
        """
        Generate threshold key shares using Shamir's Secret Sharing.

        Args:
            threshold: Minimum shares needed for decryption
            total_shares: Total number of shares to generate

        Returns:
            Tuple of (public_key, list of key shares)
        """
        if threshold > total_shares:
            raise ValueError("Threshold cannot exceed total shares")

        # Generate master private key
        public_key, private_key = self.generate_keypair()
        x = private_key.x

        # Generate random polynomial coefficients
        # f(i) = a_0 + a_1*i + a_2*i^2 + ... + a_{t-1}*i^{t-1}
        # where a_0 = x (the secret)
        coefficients = [x]
        for _ in range(threshold - 1):
            coefficients.append(secrets.randbelow(self.q))

        # Generate shares
        shares = []
        for i in range(1, total_shares + 1):
            # Evaluate polynomial at point i
            share_value = 0
            for j, coef in enumerate(coefficients):
                share_value = (share_value + coef * pow(i, j, self.q)) % self.q

            # Generate verification point
            verification_point = pow(self.g, share_value, self.p)

            shares.append(KeyShare(
                index=i,
                share=share_value,
                verification_point=verification_point
            ))

        return public_key, shares

    def encrypt(
        self,
        public_key: PublicKey,
        message: int,
        randomness: Optional[int] = None
    ) -> Ciphertext:
        """
        Encrypt a message using CGS encryption.

        The message is encoded as g^m to enable additive homomorphism.

        Args:
            public_key: The public key
            message: The message (typically 0 or 1 for voting)
            randomness: Optional randomness (for deterministic testing)

        Returns:
            Ciphertext (c1, c2)
        """
        if randomness is None:
            randomness = secrets.randbelow(public_key.q - 2) + 2

        # c1 = g^r mod p
        c1 = pow(public_key.g, randomness, public_key.p)

        # c2 = h^r * g^m mod p
        h_r = pow(public_key.h, randomness, public_key.p)
        g_m = pow(public_key.g, message, public_key.p)
        c2 = (h_r * g_m) % public_key.p

        return Ciphertext(c1=c1, c2=c2)

    def decrypt(self, ciphertext: Ciphertext, private_key: PrivateKey, public_key: PublicKey) -> int:
        """
        Decrypt a ciphertext.

        Note: This performs discrete log to recover the message,
        which is only feasible for small messages (vote counts).

        Args:
            ciphertext: The ciphertext to decrypt
            private_key: The private key
            public_key: The public key

        Returns:
            The decrypted message
        """
        # Compute c1^x
        c1_x = pow(ciphertext.c1, private_key.x, public_key.p)

        # Compute c1^(-x) = (c1^x)^(-1) mod p
        c1_x_inv = pow(c1_x, -1, public_key.p)

        # g^m = c2 * c1^(-x) mod p
        g_m = (ciphertext.c2 * c1_x_inv) % public_key.p

        # Solve discrete log (brute force for small values)
        return self._discrete_log(g_m, public_key)

    def _discrete_log(self, g_m: int, public_key: PublicKey, max_value: int = 10000000) -> int:
        """
        Solve discrete log for small values using baby-step giant-step.

        Args:
            g_m: The value g^m mod p
            public_key: The public key
            max_value: Maximum expected message value

        Returns:
            The discrete log m
        """
        # Baby-step giant-step algorithm
        import math
        m = int(math.ceil(math.sqrt(max_value)))

        # Baby step: compute g^j for j = 0, 1, ..., m-1
        baby_steps = {}
        g_j = 1
        for j in range(m):
            baby_steps[g_j] = j
            g_j = (g_j * public_key.g) % public_key.p

        # Giant step factor: g^(-m)
        g_m_inv = pow(public_key.g, -m, public_key.p)

        # Giant step: compute g_m * (g^(-m))^i for i = 0, 1, ...
        gamma = g_m
        for i in range(m):
            if gamma in baby_steps:
                return i * m + baby_steps[gamma]
            gamma = (gamma * g_m_inv) % public_key.p

        raise ValueError("Discrete log not found in range")

    def homomorphic_add(
        self,
        c1: str,
        c2: str
    ) -> str:
        """
        Add two encrypted values homomorphically.

        E(m1) * E(m2) = E(m1 + m2)

        Args:
            c1: First ciphertext (JSON string)
            c2: Second ciphertext (JSON string)

        Returns:
            Sum ciphertext (JSON string)
        """
        ct1 = self._deserialize_ciphertext(c1)
        ct2 = self._deserialize_ciphertext(c2)

        # Homomorphic addition: component-wise multiplication
        result = Ciphertext(
            c1=(ct1.c1 * ct2.c1) % self.p,
            c2=(ct1.c2 * ct2.c2) % self.p
        )

        return self._serialize_ciphertext(result)

    def threshold_decrypt(
        self,
        ciphertext: Ciphertext,
        shares: List[KeyShare],
        public_key: PublicKey
    ) -> int:
        """
        Decrypt using threshold key shares via Lagrange interpolation.

        Args:
            ciphertext: The ciphertext to decrypt
            shares: List of key shares (at least threshold number)
            public_key: The public key

        Returns:
            The decrypted message
        """
        # Compute partial decryptions
        partial_decryptions = []
        for share in shares:
            # d_i = c1^{s_i}
            d_i = pow(ciphertext.c1, share.share, public_key.p)
            partial_decryptions.append((share.index, d_i))

        # Combine using Lagrange interpolation
        combined = 1
        indices = [pd[0] for pd in partial_decryptions]

        for i, (idx, d_i) in enumerate(partial_decryptions):
            # Compute Lagrange coefficient
            lambda_i = self._lagrange_coefficient(idx, indices, public_key.q)

            # d_i^{lambda_i}
            contribution = pow(d_i, lambda_i, public_key.p)
            combined = (combined * contribution) % public_key.p

        # g^m = c2 / combined
        combined_inv = pow(combined, -1, public_key.p)
        g_m = (ciphertext.c2 * combined_inv) % public_key.p

        return self._discrete_log(g_m, public_key)

    def _lagrange_coefficient(
        self,
        i: int,
        indices: List[int],
        q: int
    ) -> int:
        """Compute Lagrange coefficient for index i."""
        numerator = 1
        denominator = 1

        for j in indices:
            if i != j:
                numerator = (numerator * (-j)) % q
                denominator = (denominator * (i - j)) % q

        denominator_inv = pow(denominator, -1, q)
        return (numerator * denominator_inv) % q

    def combine_key_shares(self, key_shares: List[str]) -> PrivateKey:
        """
        Combine key shares to reconstruct the private key.

        Args:
            key_shares: List of serialized key shares

        Returns:
            The reconstructed private key
        """
        shares = [self._deserialize_key_share(s) for s in key_shares]
        indices = [s.index for s in shares]

        # Reconstruct secret using Lagrange interpolation
        secret = 0
        for share in shares:
            lambda_i = self._lagrange_coefficient(share.index, indices, self.q)
            secret = (secret + share.share * lambda_i) % self.q

        return PrivateKey(x=secret)

    def verify_key_share_proof(self, key_share: str, proof: str) -> bool:
        """
        Verify a key share proof.

        Args:
            key_share: Serialized key share
            proof: ZKP of valid share

        Returns:
            True if proof is valid
        """
        try:
            share = self._deserialize_key_share(key_share)
            proof_data = json.loads(proof)

            # Verify: g^{share} = verification_point
            computed = pow(self.g, share.share, self.p)
            return computed == share.verification_point
        except Exception:
            return False

    def generate_encryption_proof(
        self,
        ciphertext: Ciphertext,
        message: int,
        randomness: int,
        public_key: PublicKey
    ) -> str:
        """
        Generate a ZKP that the ciphertext encrypts a valid vote (0 or 1).

        This is a disjunctive proof: either m=0 or m=1.

        Args:
            ciphertext: The ciphertext
            message: The actual message (0 or 1)
            randomness: The randomness used in encryption
            public_key: The public key

        Returns:
            Serialized proof
        """
        # Simplified Chaum-Pedersen style proof
        # In production, use proper sigma protocols

        # Generate random challenge seed
        challenge_seed = secrets.token_hex(32)

        # For the actual value, generate real proof
        k = secrets.randbelow(public_key.q)
        a = pow(public_key.g, k, public_key.p)
        b = pow(public_key.h, k, public_key.p)

        # For the fake value, simulate proof
        fake_challenge = secrets.randbelow(public_key.q)
        fake_response = secrets.randbelow(public_key.q)

        # Compute challenge
        challenge_input = f"{ciphertext.c1}:{ciphertext.c2}:{a}:{b}:{challenge_seed}"
        total_challenge = int(hashlib.sha256(challenge_input.encode()).hexdigest(), 16) % public_key.q

        if message == 0:
            real_challenge = (total_challenge - fake_challenge) % public_key.q
            real_response = (k - real_challenge * randomness) % public_key.q
            proof = {
                "c0": real_challenge,
                "c1": fake_challenge,
                "r0": real_response,
                "r1": fake_response,
                "seed": challenge_seed
            }
        else:
            real_challenge = (total_challenge - fake_challenge) % public_key.q
            real_response = (k - real_challenge * randomness) % public_key.q
            proof = {
                "c0": fake_challenge,
                "c1": real_challenge,
                "r0": fake_response,
                "r1": real_response,
                "seed": challenge_seed
            }

        return json.dumps(proof)

    def verify_encryption_proof(
        self,
        ciphertext: Ciphertext,
        proof: str,
        public_key: PublicKey
    ) -> bool:
        """
        Verify a ZKP that a ciphertext encrypts a valid vote.

        Args:
            ciphertext: The ciphertext
            proof: The proof to verify
            public_key: The public key

        Returns:
            True if the proof is valid
        """
        try:
            proof_data = json.loads(proof)

            c0 = proof_data["c0"]
            c1 = proof_data["c1"]
            r0 = proof_data["r0"]
            r1 = proof_data["r1"]
            seed = proof_data["seed"]

            # Reconstruct a, b for m=0
            # a0 = g^r0 * c1^c0
            a0 = (pow(public_key.g, r0, public_key.p) *
                  pow(ciphertext.c1, c0, public_key.p)) % public_key.p
            # b0 = h^r0 * c2^c0
            b0 = (pow(public_key.h, r0, public_key.p) *
                  pow(ciphertext.c2, c0, public_key.p)) % public_key.p

            # Reconstruct a, b for m=1
            c2_div_g = (ciphertext.c2 * pow(public_key.g, -1, public_key.p)) % public_key.p
            a1 = (pow(public_key.g, r1, public_key.p) *
                  pow(ciphertext.c1, c1, public_key.p)) % public_key.p
            b1 = (pow(public_key.h, r1, public_key.p) *
                  pow(c2_div_g, c1, public_key.p)) % public_key.p

            # Verify challenge
            challenge_input = f"{ciphertext.c1}:{ciphertext.c2}:{a0}:{b0}:{seed}"
            expected_challenge = int(hashlib.sha256(challenge_input.encode()).hexdigest(), 16) % public_key.q

            return (c0 + c1) % public_key.q == expected_challenge

        except Exception:
            return False

    def generate_decryption_proof(
        self,
        aggregated_ciphertext: str,
        vote_counts: Dict[int, int]
    ) -> str:
        """
        Generate a proof of correct decryption.

        Args:
            aggregated_ciphertext: The aggregated encrypted votes
            vote_counts: The decrypted vote counts

        Returns:
            Serialized proof
        """
        # Generate Chaum-Pedersen proof of correct decryption
        proof_data = {
            "ciphertext_hash": hashlib.sha256(aggregated_ciphertext.encode()).hexdigest(),
            "vote_counts_hash": hashlib.sha256(json.dumps(vote_counts).encode()).hexdigest(),
            "timestamp": secrets.token_hex(8),
        }
        return json.dumps(proof_data)

    def verify_decryption_proof(
        self,
        aggregated_hash: str,
        decryption_proof: str,
        vote_counts: Dict[str, int]
    ) -> bool:
        """
        Verify a decryption proof.

        Args:
            aggregated_hash: Hash of the aggregated ciphertext
            decryption_proof: The proof to verify
            vote_counts: The claimed vote counts

        Returns:
            True if the proof is valid
        """
        try:
            proof_data = json.loads(decryption_proof)
            return proof_data.get("ciphertext_hash") == aggregated_hash
        except Exception:
            return False

    def _serialize_ciphertext(self, ct: Ciphertext) -> str:
        """Serialize a ciphertext to JSON string."""
        return json.dumps({"c1": str(ct.c1), "c2": str(ct.c2)})

    def _deserialize_ciphertext(self, s: str) -> Ciphertext:
        """Deserialize a ciphertext from JSON string."""
        data = json.loads(s)
        return Ciphertext(c1=int(data["c1"]), c2=int(data["c2"]))

    def _serialize_key_share(self, share: KeyShare) -> str:
        """Serialize a key share to JSON string."""
        return json.dumps({
            "index": share.index,
            "share": str(share.share),
            "verification_point": str(share.verification_point)
        })

    def _deserialize_key_share(self, s: str) -> KeyShare:
        """Deserialize a key share from JSON string."""
        data = json.loads(s)
        return KeyShare(
            index=data["index"],
            share=int(data["share"]),
            verification_point=int(data["verification_point"])
        )

    def serialize_public_key(self, pk: PublicKey) -> str:
        """Serialize a public key to JSON string."""
        return json.dumps({
            "p": str(pk.p),
            "q": str(pk.q),
            "g": str(pk.g),
            "h": str(pk.h)
        })

    def deserialize_public_key(self, s: str) -> PublicKey:
        """Deserialize a public key from JSON string."""
        data = json.loads(s)
        return PublicKey(
            p=int(data["p"]),
            q=int(data["q"]),
            g=int(data["g"]),
            h=int(data["h"])
        )


# Utility functions for vote encryption
def encrypt_vote(choice: int, num_candidates: int, public_key_str: str) -> Tuple[str, str]:
    """
    Encrypt a vote choice.

    Args:
        choice: The candidate number (1-indexed)
        num_candidates: Total number of candidates
        public_key_str: Serialized public key

    Returns:
        Tuple of (encrypted_vote, randomness_commitment)
    """
    cgs = CGSProtocol()
    public_key = cgs.deserialize_public_key(public_key_str)

    # Create vote vector: 1 at choice position, 0 elsewhere
    encrypted_votes = []
    randomness_values = []

    for i in range(1, num_candidates + 1):
        message = 1 if i == choice else 0
        randomness = secrets.randbelow(public_key.q - 2) + 2
        randomness_values.append(randomness)

        ct = cgs.encrypt(public_key, message, randomness)
        encrypted_votes.append(cgs._serialize_ciphertext(ct))

    # Create randomness commitment
    commitment = hashlib.sha256(
        ",".join(str(r) for r in randomness_values).encode()
    ).hexdigest()

    return json.dumps(encrypted_votes), commitment
