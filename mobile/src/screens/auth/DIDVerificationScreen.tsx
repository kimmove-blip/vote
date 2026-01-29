/**
 * DID Verification Screen
 * Handles DID-based authentication
 */
import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useDispatch, useSelector } from 'react-redux';
import { AppDispatch, RootState } from '../../store';
import { loginWithDID, clearError } from '../../store/slices/authSlice';
import apiClient from '../../services/api/client';

interface Props {
  navigation: any;
}

const DIDVerificationScreen: React.FC<Props> = ({ navigation }) => {
  const dispatch = useDispatch<AppDispatch>();
  const { isLoading, error } = useSelector((state: RootState) => state.auth);

  const [step, setStep] = useState<'init' | 'connecting' | 'verifying' | 'success'>('init');
  const [challenge, setChallenge] = useState<string | null>(null);

  useEffect(() => {
    if (error) {
      Alert.alert('Authentication Error', error);
      dispatch(clearError());
    }
  }, [error, dispatch]);

  const handleConnectWallet = async () => {
    setStep('connecting');

    try {
      // Get challenge from server
      const { challenge: serverChallenge } = await apiClient.getDIDChallenge();
      setChallenge(serverChallenge);

      // In production, this would trigger the DID wallet app
      // For now, simulate the wallet connection
      setTimeout(() => {
        setStep('verifying');
        handleVerification(serverChallenge);
      }, 1500);
    } catch (error) {
      Alert.alert('Error', 'Failed to connect to server');
      setStep('init');
    }
  };

  const handleVerification = async (serverChallenge: string) => {
    try {
      // In production, this VP would come from the DID wallet
      // This is a mock VP for demonstration
      const mockVP = {
        '@context': ['https://www.w3.org/2018/credentials/v1'],
        type: ['VerifiablePresentation'],
        holder: 'did:omni:123456789abcdefghi',
        verifiableCredential: [
          {
            '@context': ['https://www.w3.org/2018/credentials/v1'],
            type: ['VerifiableCredential', 'VoterCredential'],
            issuer: 'did:omni:nec-issuer',
            credentialSubject: {
              id: 'did:omni:123456789abcdefghi',
              name: 'Voter Name',
              eligibility: true,
            },
          },
        ],
        proof: {
          type: 'Ed25519Signature2020',
          challenge: serverChallenge,
          created: new Date().toISOString(),
          proofPurpose: 'authentication',
          verificationMethod: 'did:omni:123456789abcdefghi#key-1',
          jws: 'mock-signature',
        },
      };

      // Dispatch login action
      const result = await dispatch(
        loginWithDID({
          verifiablePresentation: mockVP,
          challenge: serverChallenge,
        })
      ).unwrap();

      setStep('success');

      // Navigate to biometric setup
      setTimeout(() => {
        navigation.replace('BiometricAuth');
      }, 1000);
    } catch (error) {
      setStep('init');
    }
  };

  const renderStep = () => {
    switch (step) {
      case 'init':
        return (
          <>
            <View style={styles.iconContainer}>
              <Text style={styles.icon}>🪪</Text>
            </View>
            <Text style={styles.title}>Verify Your Identity</Text>
            <Text style={styles.description}>
              Connect your DID wallet to verify your identity and eligibility to vote.
            </Text>
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={handleConnectWallet}
              accessibilityRole="button"
              accessibilityLabel="Connect DID Wallet"
            >
              <Text style={styles.primaryButtonText}>Connect DID Wallet</Text>
            </TouchableOpacity>
          </>
        );

      case 'connecting':
        return (
          <>
            <ActivityIndicator size="large" color="#1a56db" />
            <Text style={styles.statusText}>Connecting to DID Wallet...</Text>
            <Text style={styles.subStatusText}>
              Please approve the connection request in your wallet app
            </Text>
          </>
        );

      case 'verifying':
        return (
          <>
            <ActivityIndicator size="large" color="#1a56db" />
            <Text style={styles.statusText}>Verifying Identity...</Text>
            <Text style={styles.subStatusText}>
              Validating your credentials with the issuer
            </Text>
          </>
        );

      case 'success':
        return (
          <>
            <View style={[styles.iconContainer, styles.successIcon]}>
              <Text style={styles.icon}>✓</Text>
            </View>
            <Text style={styles.title}>Verification Complete</Text>
            <Text style={styles.description}>
              Your identity has been verified. Setting up biometric authentication...
            </Text>
          </>
        );
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity
          onPress={() => navigation.goBack()}
          accessibilityRole="button"
          accessibilityLabel="Go back"
          style={styles.backButton}
        >
          <Text style={styles.backButtonText}>← Back</Text>
        </TouchableOpacity>
      </View>

      <View style={styles.content}>{renderStep()}</View>

      <View style={styles.footer}>
        <Text style={styles.securityNote}>
          🔒 Your identity data is encrypted and never stored on our servers
        </Text>
      </View>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  header: {
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  backButton: {
    padding: 8,
  },
  backButtonText: {
    fontSize: 16,
    color: '#1a56db',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  iconContainer: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#E5EDFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  successIcon: {
    backgroundColor: '#D1FAE5',
  },
  icon: {
    fontSize: 36,
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 32,
    paddingHorizontal: 24,
  },
  primaryButton: {
    width: '100%',
    backgroundColor: '#1a56db',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
  },
  primaryButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  statusText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#111827',
    marginTop: 24,
    textAlign: 'center',
  },
  subStatusText: {
    fontSize: 14,
    color: '#6B7280',
    marginTop: 8,
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  footer: {
    paddingHorizontal: 24,
    paddingVertical: 16,
  },
  securityNote: {
    fontSize: 12,
    color: '#6B7280',
    textAlign: 'center',
  },
});

export default DIDVerificationScreen;
