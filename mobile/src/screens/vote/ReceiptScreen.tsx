/**
 * Receipt Screen - Vote confirmation and verification
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  ScrollView,
  Share,
  Clipboard,
} from 'react-native';
import { useSelector } from 'react-redux';
import { RootState } from '../../store';

interface Props {
  navigation: any;
}

const ReceiptScreen: React.FC<Props> = ({ navigation }) => {
  const { receipt } = useSelector((state: RootState) => state.vote);

  if (!receipt) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centerContent}>
          <Text style={styles.errorText}>Receipt not available</Text>
        </View>
      </SafeAreaView>
    );
  }

  const handleCopyCode = () => {
    Clipboard.setString(receipt.verificationCode);
    // In production, show a toast notification
  };

  const handleShare = async () => {
    try {
      await Share.share({
        message: `My vote verification code: ${receipt.verificationCode}\n\nVerify at: https://voting.example.com/verify`,
      });
    } catch (error) {
      console.error('Share error:', error);
    }
  };

  const handleDone = () => {
    navigation.reset({
      index: 0,
      routes: [{ name: 'MainTabs' }],
    });
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView contentContainerStyle={styles.scrollContent}>
        <View style={styles.successIcon}>
          <Text style={styles.successEmoji}>✓</Text>
        </View>

        <Text style={styles.title} accessibilityRole="header">
          Vote Submitted Successfully
        </Text>

        <Text style={styles.subtitle}>
          Your vote has been encrypted and recorded on the blockchain
        </Text>

        <View style={styles.receiptCard}>
          <Text style={styles.receiptTitle}>Verification Code</Text>

          <TouchableOpacity
            style={styles.codeContainer}
            onPress={handleCopyCode}
            accessibilityRole="button"
            accessibilityLabel={`Verification code: ${receipt.verificationCode}. Tap to copy.`}
          >
            <Text style={styles.verificationCode}>{receipt.verificationCode}</Text>
            <Text style={styles.copyHint}>Tap to copy</Text>
          </TouchableOpacity>

          <Text style={styles.receiptNote}>
            Save this code! You can use it to verify your vote was recorded correctly.
          </Text>
        </View>

        <View style={styles.detailsCard}>
          <Text style={styles.detailsTitle}>Transaction Details</Text>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Election</Text>
            <Text style={styles.detailValue}>{receipt.electionTitle}</Text>
          </View>

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Vote Hash</Text>
            <Text style={styles.detailValueMono} numberOfLines={1}>
              {receipt.encryptedVoteHash.slice(0, 16)}...
            </Text>
          </View>

          {receipt.blockchainTxId && (
            <View style={styles.detailRow}>
              <Text style={styles.detailLabel}>Blockchain TX</Text>
              <Text style={styles.detailValueMono} numberOfLines={1}>
                {receipt.blockchainTxId.slice(0, 16)}...
              </Text>
            </View>
          )}

          <View style={styles.detailRow}>
            <Text style={styles.detailLabel}>Timestamp</Text>
            <Text style={styles.detailValue}>
              {new Date(receipt.createdAt).toLocaleString()}
            </Text>
          </View>
        </View>

        <View style={styles.verificationInfo}>
          <Text style={styles.verificationTitle}>How to Verify Your Vote</Text>
          <Text style={styles.verificationStep}>
            1. Go to Verification tab or visit voting.example.com/verify
          </Text>
          <Text style={styles.verificationStep}>
            2. Enter your verification code
          </Text>
          <Text style={styles.verificationStep}>
            3. Confirm your encrypted vote was recorded on the blockchain
          </Text>
        </View>

        <View style={styles.buttonContainer}>
          <TouchableOpacity
            style={styles.shareButton}
            onPress={handleShare}
            accessibilityRole="button"
            accessibilityLabel="Share verification code"
          >
            <Text style={styles.shareButtonText}>Share Code</Text>
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.doneButton}
            onPress={handleDone}
            accessibilityRole="button"
            accessibilityLabel="Return to home screen"
          >
            <Text style={styles.doneButtonText}>Done</Text>
          </TouchableOpacity>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#F9FAFB',
  },
  centerContent: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorText: {
    fontSize: 16,
    color: '#6B7280',
  },
  scrollContent: {
    padding: 24,
    alignItems: 'center',
  },
  successIcon: {
    width: 80,
    height: 80,
    borderRadius: 40,
    backgroundColor: '#D1FAE5',
    justifyContent: 'center',
    alignItems: 'center',
    marginBottom: 24,
  },
  successEmoji: {
    fontSize: 40,
    color: '#059669',
  },
  title: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#111827',
    textAlign: 'center',
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: '#6B7280',
    textAlign: 'center',
    marginBottom: 32,
  },
  receiptCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 24,
    width: '100%',
    marginBottom: 16,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  receiptTitle: {
    fontSize: 14,
    color: '#6B7280',
    marginBottom: 12,
  },
  codeContainer: {
    backgroundColor: '#F3F4F6',
    borderRadius: 12,
    padding: 16,
    width: '100%',
    alignItems: 'center',
    marginBottom: 16,
  },
  verificationCode: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#1a56db',
    fontFamily: 'Courier',
    letterSpacing: 2,
  },
  copyHint: {
    fontSize: 12,
    color: '#9CA3AF',
    marginTop: 4,
  },
  receiptNote: {
    fontSize: 14,
    color: '#F59E0B',
    textAlign: 'center',
    backgroundColor: '#FEF3C7',
    padding: 12,
    borderRadius: 8,
    width: '100%',
  },
  detailsCard: {
    backgroundColor: '#FFFFFF',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#E5E7EB',
  },
  detailsTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#111827',
    marginBottom: 16,
  },
  detailRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 8,
    borderBottomWidth: 1,
    borderBottomColor: '#F3F4F6',
  },
  detailLabel: {
    fontSize: 14,
    color: '#6B7280',
  },
  detailValue: {
    fontSize: 14,
    color: '#111827',
    fontWeight: '500',
    flex: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
  detailValueMono: {
    fontSize: 12,
    color: '#111827',
    fontFamily: 'Courier',
    flex: 1,
    textAlign: 'right',
    marginLeft: 12,
  },
  verificationInfo: {
    backgroundColor: '#EFF6FF',
    borderRadius: 16,
    padding: 20,
    width: '100%',
    marginBottom: 24,
  },
  verificationTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#1E40AF',
    marginBottom: 12,
  },
  verificationStep: {
    fontSize: 14,
    color: '#3B82F6',
    marginBottom: 8,
    lineHeight: 20,
  },
  buttonContainer: {
    width: '100%',
    gap: 12,
  },
  shareButton: {
    backgroundColor: '#F3F4F6',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
  },
  shareButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#374151',
  },
  doneButton: {
    backgroundColor: '#1a56db',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    minHeight: 48,
  },
  doneButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
});

export default ReceiptScreen;
