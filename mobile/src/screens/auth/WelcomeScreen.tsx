/**
 * Welcome Screen - Entry point for authentication
 */
import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  SafeAreaView,
  Image,
  AccessibilityInfo,
} from 'react-native';

interface Props {
  navigation: any;
}

const WelcomeScreen: React.FC<Props> = ({ navigation }) => {
  const handleDIDLogin = () => {
    navigation.navigate('DIDVerification');
  };

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.content}>
        <View style={styles.logoContainer}>
          <View style={styles.logoPlaceholder}>
            <Text style={styles.logoText}>VOTE</Text>
          </View>
        </View>

        <Text
          style={styles.title}
          accessibilityRole="header"
          accessibilityLabel="Blockchain Voting System"
        >
          Blockchain Voting System
        </Text>

        <Text style={styles.subtitle}>
          Secure, transparent, and verifiable electronic voting
        </Text>

        <View style={styles.features}>
          <FeatureItem
            icon="shield"
            text="End-to-end encryption"
          />
          <FeatureItem
            icon="check"
            text="Verifiable on blockchain"
          />
          <FeatureItem
            icon="lock"
            text="Anonymous voting"
          />
        </View>

        <TouchableOpacity
          style={styles.primaryButton}
          onPress={handleDIDLogin}
          accessibilityRole="button"
          accessibilityLabel="Login with DID"
          accessibilityHint="Opens the DID verification screen"
        >
          <Text style={styles.primaryButtonText}>Login with DID</Text>
        </TouchableOpacity>

        <Text style={styles.infoText}>
          You need a verified DID (Decentralized Identity) to participate in voting.
        </Text>
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>
          Powered by Hyperledger Fabric
        </Text>
        <Text style={styles.versionText}>
          Version 1.0.0
        </Text>
      </View>
    </SafeAreaView>
  );
};

interface FeatureItemProps {
  icon: string;
  text: string;
}

const FeatureItem: React.FC<FeatureItemProps> = ({ icon, text }) => (
  <View style={styles.featureItem} accessibilityLabel={text}>
    <View style={styles.featureIcon}>
      <Text style={styles.featureIconText}>
        {icon === 'shield' ? '🛡️' : icon === 'check' ? '✓' : '🔒'}
      </Text>
    </View>
    <Text style={styles.featureText}>{text}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#FFFFFF',
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoContainer: {
    marginBottom: 32,
  },
  logoPlaceholder: {
    width: 100,
    height: 100,
    borderRadius: 20,
    backgroundColor: '#1a56db',
    justifyContent: 'center',
    alignItems: 'center',
  },
  logoText: {
    fontSize: 24,
    fontWeight: 'bold',
    color: '#FFFFFF',
  },
  title: {
    fontSize: 28,
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
  features: {
    width: '100%',
    marginBottom: 32,
  },
  featureItem: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: '#F9FAFB',
    borderRadius: 12,
    marginBottom: 12,
  },
  featureIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: '#E5EDFF',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  featureIconText: {
    fontSize: 18,
  },
  featureText: {
    fontSize: 16,
    color: '#374151',
    flex: 1,
  },
  primaryButton: {
    width: '100%',
    backgroundColor: '#1a56db',
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
    marginBottom: 16,
    // Accessibility: minimum touch target size
    minHeight: 48,
  },
  primaryButtonText: {
    fontSize: 18,
    fontWeight: '600',
    color: '#FFFFFF',
  },
  infoText: {
    fontSize: 14,
    color: '#6B7280',
    textAlign: 'center',
    paddingHorizontal: 24,
  },
  footer: {
    paddingVertical: 16,
    alignItems: 'center',
  },
  footerText: {
    fontSize: 14,
    color: '#9CA3AF',
  },
  versionText: {
    fontSize: 12,
    color: '#D1D5DB',
    marginTop: 4,
  },
});

export default WelcomeScreen;
