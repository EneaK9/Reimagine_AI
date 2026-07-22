import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../screens/legal_document_screen.dart';
import '../../theme/app_theme.dart';

/// Compact Privacy / Terms links for the bottom of auth forms.
class AuthLegalLinks extends StatelessWidget {
  const AuthLegalLinks({super.key});

  void _open(BuildContext context, Widget screen) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => screen),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        _link(context, 'Privacy Policy', const PrivacyPolicyScreen()),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Text(
            '·',
            style: GoogleFonts.interTight(
              fontSize: 13,
              color: AppTheme.authMuted,
            ),
          ),
        ),
        _link(context, 'Terms of Service', const TermsOfServiceScreen()),
      ],
    );
  }

  Widget _link(BuildContext context, String label, Widget screen) {
    return TextButton(
      onPressed: () => _open(context, screen),
      style: TextButton.styleFrom(
        padding: EdgeInsets.zero,
        minimumSize: Size.zero,
        tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        overlayColor: Colors.transparent,
        foregroundColor: AppTheme.authMuted,
      ),
      child: Text(
        label,
        style: GoogleFonts.interTight(
          fontSize: 12.5,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }
}
