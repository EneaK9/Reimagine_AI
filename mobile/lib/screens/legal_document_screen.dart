import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../theme/app_theme.dart';

/// Shared layout for Privacy Policy / Terms of Service.
class LegalDocumentScreen extends StatelessWidget {
  const LegalDocumentScreen({
    super.key,
    required this.title,
    required this.sections,
    this.lastUpdated = 'July 22, 2026',
  });

  final String title;
  final List<LegalSection> sections;
  final String lastUpdated;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.surface,
      appBar: AppBar(
        backgroundColor: AppTheme.surface,
        surfaceTintColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_rounded, color: AppTheme.ink),
          onPressed: () => Navigator.of(context).maybePop(),
        ),
        title: Text(
          title,
          style: GoogleFonts.interTight(
            fontSize: 16,
            fontWeight: FontWeight.w600,
            color: AppTheme.ink,
          ),
        ),
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1),
          child: Container(height: 1, color: AppTheme.gridLine),
        ),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 720),
          child: ListView(
            padding: const EdgeInsets.fromLTRB(24, 28, 24, 48),
            children: [
              Text(
                title,
                style: GoogleFonts.dmSerifDisplay(
                  fontSize: 34,
                  height: 1.15,
                  color: AppTheme.ink,
                ),
              ),
              const SizedBox(height: 10),
              Text(
                'Last updated: $lastUpdated',
                style: GoogleFonts.interTight(
                  fontSize: 13,
                  color: AppTheme.textMuted,
                ),
              ),
              const SizedBox(height: 28),
              for (final section in sections) ...[
                Text(
                  section.heading,
                  style: GoogleFonts.interTight(
                    fontSize: 17,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.ink,
                  ),
                ),
                const SizedBox(height: 10),
                Text(
                  section.body,
                  style: GoogleFonts.interTight(
                    fontSize: 14.5,
                    height: 1.65,
                    color: AppTheme.textSecondary,
                  ),
                ),
                const SizedBox(height: 24),
              ],
              Text(
                'Questions? Contact us at privacy@reimagine.ai.',
                style: GoogleFonts.interTight(
                  fontSize: 13.5,
                  color: AppTheme.textMuted,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class LegalSection {
  const LegalSection(this.heading, this.body);

  final String heading;
  final String body;
}

/// Privacy Policy for ReimagineAI.
class PrivacyPolicyScreen extends StatelessWidget {
  const PrivacyPolicyScreen({super.key});

  static const List<LegalSection> _sections = [
    LegalSection(
      '1. Who we are',
      'ReimagineAI (“we”, “us”) provides AI-assisted interior design tools that '
          'help you visualize changes to rooms from photos and chat. This Privacy '
          'Policy explains what information we collect, how we use it, and the '
          'choices you have.',
    ),
    LegalSection(
      '2. Information we collect',
      'Account information: email, username, and password credentials (stored '
          'as a salted hash).\n\n'
          'Content you provide: chat messages, room photos you upload, design '
          'preferences, and generated or edited images associated with your '
          'account.\n\n'
          'Usage data: basic technical logs such as API requests, device/browser '
          'type, and timestamps needed to operate and secure the service.',
    ),
    LegalSection(
      '3. How we use your information',
      'We use your information to create and manage your account, run the chat '
          'and image-editing features, save your conversations and designs, '
          'improve product quality and reliability, and communicate about '
          'security or service changes. We do not sell your personal information.',
    ),
    LegalSection(
      '4. AI processing',
      'Photos and prompts you submit may be sent to third-party AI providers '
          '(for example, language and image models) solely to generate responses '
          'and redesigned images for you. Do not upload images of other people '
          'without their permission, or content you are not allowed to share.',
    ),
    LegalSection(
      '5. Storage and retention',
      'Account and conversation data are stored in our database. Images and '
          'related design context may be retained while your account is active '
          'so you can resume projects. You may request deletion of your account '
          'and associated content by contacting us.',
    ),
    LegalSection(
      '6. Sharing',
      'We share data with service providers that help us host the app, run AI '
          'features, and operate infrastructure, under agreements that limit use '
          'to providing those services. We may disclose information if required '
          'by law or to protect users and the service.',
    ),
    LegalSection(
      '7. Your choices',
      'You can update account details, log out to invalidate your session '
          'token, and stop using the service at any time. You may also request '
          'access to or deletion of personal data we hold about you, subject to '
          'applicable law.',
    ),
    LegalSection(
      '8. Security',
      'We use reasonable technical and organizational measures to protect your '
          'data, including hashed passwords and authenticated API access. No '
          'method of transmission or storage is completely secure.',
    ),
    LegalSection(
      '9. Children',
      'ReimagineAI is not directed to children under 13 (or the minimum age in '
          'your jurisdiction). We do not knowingly collect personal information '
          'from children.',
    ),
    LegalSection(
      '10. Changes',
      'We may update this Privacy Policy from time to time. We will revise the '
          '“Last updated” date and, when changes are material, provide additional '
          'notice where appropriate.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return const LegalDocumentScreen(
      title: 'Privacy Policy',
      sections: _sections,
    );
  }
}

/// Terms of Service for ReimagineAI.
class TermsOfServiceScreen extends StatelessWidget {
  const TermsOfServiceScreen({super.key});

  static const List<LegalSection> _sections = [
    LegalSection(
      '1. Agreement',
      'By creating an account or using ReimagineAI, you agree to these Terms of '
          'Service. If you do not agree, do not use the service.',
    ),
    LegalSection(
      '2. The service',
      'ReimagineAI offers AI-assisted tools to analyze room photos, chat about '
          'design ideas, and generate or edit interior design images. Features '
          'may change, improve, or be discontinued as the product evolves.',
    ),
    LegalSection(
      '3. Accounts',
      'You must provide accurate registration information and keep your '
          'credentials secure. You are responsible for activity under your '
          'account. Notify us promptly if you suspect unauthorized access.',
    ),
    LegalSection(
      '4. Acceptable use',
      'You agree not to misuse the service, including by uploading unlawful or '
          'infringing content, attempting to reverse engineer or overload the '
          'system, using outputs to harm others, or violating applicable laws. '
          'We may suspend or terminate accounts that violate these terms.',
    ),
    LegalSection(
      '5. Your content',
      'You retain rights to photos and text you upload. You grant us a limited '
          'license to host, process, and display that content as needed to '
          'provide the service (including sending it to AI providers for '
          'generation). You represent that you have the rights needed to upload '
          'and process that content.',
    ),
    LegalSection(
      '6. AI outputs',
      'Generated designs are suggestions for inspiration and visualization. '
          'They may be inaccurate, incomplete, or unsuitable for real-world '
          'construction. You are responsible for verifying measurements, '
          'safety, permits, and professional advice before making physical '
          'changes to a space.',
    ),
    LegalSection(
      '7. Intellectual property',
      'The ReimagineAI name, branding, software, and interface are owned by us '
          'or our licensors. Except for your own content and rights granted by '
          'law, you may not copy or redistribute our materials without '
          'permission.',
    ),
    LegalSection(
      '8. Disclaimers',
      'THE SERVICE IS PROVIDED “AS IS” WITHOUT WARRANTIES OF ANY KIND, EXPRESS '
          'OR IMPLIED, INCLUDING MERCHANTABILITY, FITNESS FOR A PARTICULAR '
          'PURPOSE, AND NON-INFRINGEMENT, TO THE MAXIMUM EXTENT PERMITTED BY LAW.',
    ),
    LegalSection(
      '9. Limitation of liability',
      'To the maximum extent permitted by law, ReimagineAI and its providers '
          'will not be liable for indirect, incidental, special, consequential, '
          'or punitive damages, or for loss of data, profits, or business, '
          'arising from your use of the service.',
    ),
    LegalSection(
      '10. Changes and termination',
      'We may update these Terms and will update the “Last updated” date when '
          'we do. Continued use after changes means you accept the revised '
          'Terms. You may stop using the service at any time; we may suspend or '
          'end access for violations or operational reasons.',
    ),
    LegalSection(
      '11. Contact',
      'For questions about these Terms, contact privacy@reimagine.ai.',
    ),
  ];

  @override
  Widget build(BuildContext context) {
    return const LegalDocumentScreen(
      title: 'Terms of Service',
      sections: _sections,
    );
  }
}
