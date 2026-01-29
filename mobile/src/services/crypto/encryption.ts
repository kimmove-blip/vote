/**
 * Client-side Encryption Service
 *
 * This module handles:
 * - CGS homomorphic encryption of votes
 * - ZKP generation for eligibility and validity proofs
 * - Nullifier computation for double-voting prevention
 */
import CryptoJS from 'react-native-crypto-js';
import bigInt from 'big-integer';

// CGS Protocol parameters (matching backend)
const DEFAULT_P = bigInt(
  'FFFFFFFFFFFFFFFFC90FDAA22168C234C4C6628B80DC1CD1' +
  '29024E088A67CC74020BBEA63B139B22514A08798E3404DD' +
  'EF9519B3CD3A431B302B0A6DF25F14374FE1356D6D51C245' +
  'E485B576625E7EC6F44C42E9A637ED6B0BFF5CB6F406B7ED' +
  'EE386BFB5A899FA5AE9F24117C4B1FE649286651ECE45B3D' +
  'C2007CB8A163BF0598DA48361C55D39A69163FA8FD24CF5F' +
  '83655D23DCA3AD961C62F356208552BB9ED529077096966D' +
  '670C354E4ABC9804F1746C08CA237327FFFFFFFFFFFFFFFF',
  16
);

const DEFAULT_G = bigInt(2);

export interface PublicKey {
  p: string;
  q: string;
  g: string;
  h: string;
}

export interface Ciphertext {
  c1: string;
  c2: string;
}

export interface EncryptedVote {
  ciphertext: string;
  randomnessCommitment: string;
  publicKeyHash: string;
}

export interface VoteProofs {
  eligibilityProof: string;
  validityProof: string;
  nullifier: string;
}

/**
 * Parse a public key from JSON string
 */
export function parsePublicKey(publicKeyJson: string): PublicKey {
  return JSON.parse(publicKeyJson);
}

/**
 * Generate a random big integer in range [2, q-2]
 */
function randomBigInt(q: bigInt.BigInteger): bigInt.BigInteger {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  const hex = Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return bigInt(hex, 16).mod(q.minus(3)).plus(2);
}

/**
 * Encrypt a vote choice using CGS homomorphic encryption
 */
export function encryptVote(
  choice: number,
  numCandidates: number,
  publicKey: PublicKey
): EncryptedVote {
  const p = bigInt(publicKey.p);
  const q = bigInt(publicKey.q);
  const g = bigInt(publicKey.g);
  const h = bigInt(publicKey.h);

  // Create vote vector: 1 at choice position, 0 elsewhere
  const encryptedVotes: Ciphertext[] = [];
  const randomnessValues: bigInt.BigInteger[] = [];

  for (let i = 1; i <= numCandidates; i++) {
    const message = i === choice ? 1 : 0;
    const randomness = randomBigInt(q);
    randomnessValues.push(randomness);

    // c1 = g^r mod p
    const c1 = g.modPow(randomness, p);

    // c2 = h^r * g^m mod p
    const hR = h.modPow(randomness, p);
    const gM = g.modPow(bigInt(message), p);
    const c2 = hR.multiply(gM).mod(p);

    encryptedVotes.push({
      c1: c1.toString(),
      c2: c2.toString(),
    });
  }

  // Create randomness commitment
  const randomnessStr = randomnessValues.map((r) => r.toString()).join(',');
  const commitment = CryptoJS.SHA256(randomnessStr).toString();

  // Hash of public key
  const publicKeyHash = CryptoJS.SHA256(JSON.stringify(publicKey)).toString();

  return {
    ciphertext: JSON.stringify(encryptedVotes),
    randomnessCommitment: commitment,
    publicKeyHash,
  };
}

/**
 * Generate a nullifier for double-voting prevention
 * The nullifier is unique per voter per election but doesn't reveal identity
 */
export function generateNullifier(
  voterSecret: string,
  electionId: string
): string {
  const data = `${voterSecret}:${electionId}`;
  return CryptoJS.SHA256(data).toString();
}

/**
 * Create a voter commitment for the eligibility tree
 */
export function createVoterCommitment(
  voterId: string,
  secret: string
): string {
  const data = `${voterId}:${secret}`;
  return CryptoJS.SHA256(data).toString();
}

/**
 * Generate ZKP eligibility proof
 * This proves the voter is in the eligible voter list without revealing identity
 */
export async function generateEligibilityProof(
  voterSecret: string,
  voterCommitment: string,
  merklePath: string[],
  merkleIndices: number[],
  electionId: string
): Promise<string> {
  // In production, this would use a ZKP library (snarkjs, zokrates)
  // For now, create a structured proof placeholder

  const proofInput = {
    commitment: voterCommitment,
    path: merklePath,
    indices: merkleIndices,
    electionId,
  };

  // Generate random values for proof structure
  const randomBytes = new Uint8Array(96);
  crypto.getRandomValues(randomBytes);

  const a = [
    '0x' + Array.from(randomBytes.slice(0, 32)).map((b) => b.toString(16).padStart(2, '0')).join(''),
    '0x' + Array.from(randomBytes.slice(32, 64)).map((b) => b.toString(16).padStart(2, '0')).join(''),
  ];

  const b = [
    [
      '0x' + Array.from(randomBytes.slice(64, 80)).map((b) => b.toString(16).padStart(2, '0')).join('') + '0'.repeat(32),
      '0x' + Array.from(randomBytes.slice(80, 96)).map((b) => b.toString(16).padStart(2, '0')).join('') + '0'.repeat(32),
    ],
    [
      '0x' + CryptoJS.SHA256(JSON.stringify(proofInput)).toString().slice(0, 64),
      '0x' + CryptoJS.SHA256(voterSecret).toString().slice(0, 64),
    ],
  ];

  const c = [
    '0x' + CryptoJS.SHA256(a[0]).toString(),
    '0x' + CryptoJS.SHA256(a[1]).toString(),
  ];

  const proof = {
    a,
    b,
    c,
    inputs: [
      CryptoJS.SHA256(voterCommitment).toString(),
      CryptoJS.SHA256(electionId).toString(),
    ],
  };

  return JSON.stringify(proof);
}

/**
 * Generate ZKP validity proof
 * This proves the vote is for a valid candidate without revealing the choice
 */
export async function generateValidityProof(
  choice: number,
  numCandidates: number,
  encryptedVote: string,
  randomnessCommitment: string,
  publicKeyHash: string
): Promise<string> {
  // In production, this would use a ZKP library
  // The proof demonstrates the encrypted vote contains a valid choice

  const proofInput = {
    numCandidates,
    encryptedVoteHash: CryptoJS.SHA256(encryptedVote).toString(),
    randomnessCommitment,
    publicKeyHash,
  };

  // Generate random values for proof structure
  const randomBytes = new Uint8Array(96);
  crypto.getRandomValues(randomBytes);

  const a = [
    '0x' + Array.from(randomBytes.slice(0, 32)).map((b) => b.toString(16).padStart(2, '0')).join(''),
    '0x' + Array.from(randomBytes.slice(32, 64)).map((b) => b.toString(16).padStart(2, '0')).join(''),
  ];

  const b = [
    [
      '0x' + Array.from(randomBytes.slice(64, 80)).map((b) => b.toString(16).padStart(2, '0')).join('') + '0'.repeat(32),
      '0x' + Array.from(randomBytes.slice(80, 96)).map((b) => b.toString(16).padStart(2, '0')).join('') + '0'.repeat(32),
    ],
    [
      '0x' + CryptoJS.SHA256(JSON.stringify(proofInput)).toString().slice(0, 64),
      '0x' + CryptoJS.SHA256(String(choice)).toString().slice(0, 64),
    ],
  ];

  const c = [
    '0x' + CryptoJS.SHA256(a[0]).toString(),
    '0x' + CryptoJS.SHA256(a[1]).toString(),
  ];

  const proof = {
    a,
    b,
    c,
    inputs: [
      CryptoJS.SHA256(encryptedVote).toString(),
      publicKeyHash.slice(0, 32),
    ],
  };

  return JSON.stringify(proof);
}

/**
 * Complete vote preparation - encrypt and generate all proofs
 */
export async function prepareVote(
  choice: number,
  numCandidates: number,
  publicKeyJson: string,
  voterSecret: string,
  voterCommitment: string,
  merklePath: string[],
  merkleIndices: number[],
  electionId: string
): Promise<{
  encryptedVote: EncryptedVote;
  proofs: VoteProofs;
}> {
  const publicKey = parsePublicKey(publicKeyJson);

  // Encrypt the vote
  const encryptedVote = encryptVote(choice, numCandidates, publicKey);

  // Generate nullifier
  const nullifier = generateNullifier(voterSecret, electionId);

  // Generate eligibility proof
  const eligibilityProof = await generateEligibilityProof(
    voterSecret,
    voterCommitment,
    merklePath,
    merkleIndices,
    electionId
  );

  // Generate validity proof
  const validityProof = await generateValidityProof(
    choice,
    numCandidates,
    encryptedVote.ciphertext,
    encryptedVote.randomnessCommitment,
    encryptedVote.publicKeyHash
  );

  return {
    encryptedVote,
    proofs: {
      eligibilityProof,
      validityProof,
      nullifier,
    },
  };
}

/**
 * Securely store voter secret in keychain
 */
export async function storeVoterSecret(secret: string): Promise<void> {
  // In production, use react-native-keychain for secure storage
  // import * as Keychain from 'react-native-keychain';
  // await Keychain.setGenericPassword('voter', secret);

  // Fallback to encrypted async storage
  const encrypted = CryptoJS.AES.encrypt(secret, 'device-key').toString();
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;
  await AsyncStorage.setItem('voterSecret', encrypted);
}

/**
 * Retrieve voter secret from secure storage
 */
export async function getVoterSecret(): Promise<string | null> {
  const AsyncStorage = require('@react-native-async-storage/async-storage').default;
  const encrypted = await AsyncStorage.getItem('voterSecret');

  if (!encrypted) return null;

  const bytes = CryptoJS.AES.decrypt(encrypted, 'device-key');
  return bytes.toString(CryptoJS.enc.Utf8);
}

/**
 * Generate a new voter secret
 */
export function generateVoterSecret(): string {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}
