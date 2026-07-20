import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../circle_arrow_button.dart';
import '../decorations.dart';
import '../landing_section.dart';

class FooterCta extends StatelessWidget {
  const FooterCta({super.key, required this.onCollaborate});

  final VoidCallback onCollaborate;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 800;

    return ColoredBox(
      color: AppTheme.landingAlt,
      child: Stack(
        children: [
          Positioned(
            top: 0,
            right: 0,
            bottom: 0,
            width: MediaQuery.sizeOf(context).width * 0.35,
            child: ClipPath(
              clipper: const NotchedCornerClipper(
                corner: NotchCorner.topLeft,
                notchSize: 80,
              ),
              child: Container(color: const Color(0xFFD6D4CD)),
            ),
          ),
          LandingSection(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                wide
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: Text(
                              'Are You Prepared To Reimagine Your Space',
                              style: GoogleFonts.interTight(
                                fontSize: 40,
                                fontWeight: FontWeight.w700,
                                height: 1.15,
                                letterSpacing: -0.6,
                                color: AppTheme.ink,
                              ),
                            ),
                          ),
                          const SizedBox(width: 24),
                          CircleArrowButton(onPressed: onCollaborate),
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'Are You Prepared To Reimagine Your Space',
                            style: GoogleFonts.interTight(
                              fontSize: 32,
                              fontWeight: FontWeight.w700,
                              height: 1.15,
                              color: AppTheme.ink,
                            ),
                          ),
                          const SizedBox(height: 20),
                          CircleArrowButton(onPressed: onCollaborate),
                        ],
                      ),
                const SizedBox(height: 56),
                wide
                    ? Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Expanded(
                            child: _infoCol(
                              'Address',
                              'Remote-first\nEverywhere you design',
                            ),
                          ),
                          Expanded(
                            child: _infoCol(
                              'Contact',
                              'hello@reimagineai.app\n@reimagineai',
                            ),
                          ),
                          Expanded(
                            child: _infoCol(
                              'Office Hours',
                              'Mon – Fri\n09:00 – 18:00',
                            ),
                          ),
                        ],
                      )
                    : Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _infoCol(
                            'Address',
                            'Remote-first\nEverywhere you design',
                          ),
                          const SizedBox(height: 24),
                          _infoCol(
                            'Contact',
                            'hello@reimagineai.app\n@reimagineai',
                          ),
                          const SizedBox(height: 24),
                          _infoCol(
                            'Office Hours',
                            'Mon – Fri\n09:00 – 18:00',
                          ),
                        ],
                      ),
                const SizedBox(height: 64),
                Align(
                  alignment: Alignment.centerRight,
                  child: Opacity(
                    opacity: 0.35,
                    child: LandingWordmark(
                      color: AppTheme.watermark,
                      fontSize: 42,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _infoCol(String title, String body) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: GoogleFonts.interTight(
            fontSize: 16,
            fontWeight: FontWeight.w700,
            color: AppTheme.ink,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          body,
          style: GoogleFonts.interTight(
            fontSize: 14,
            height: 1.55,
            color: AppTheme.textSecondary,
          ),
        ),
      ],
    );
  }
}
