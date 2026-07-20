import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../decorations.dart';
import '../landing_section.dart';

class LogosStrip extends StatelessWidget {
  const LogosStrip({super.key});

  static const _logos = [
    'OpenAI',
    'GPT-4',
    'DALL·E 3',
    'FastAPI',
    'Flutter',
  ];

  @override
  Widget build(BuildContext context) {
    return LandingSection(
      padding: const EdgeInsets.symmetric(horizontal: 0, vertical: 0),
      child: SizedBox(
        height: 88,
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: const GridLinesPainter(
                  columnCount: 5,
                  rowCount: 1,
                  showCrosshairs: true,
                ),
              ),
            ),
            Row(
              children: [
                for (final logo in _logos)
                  Expanded(
                    child: Center(
                      child: Text(
                        logo,
                        style: GoogleFonts.interTight(
                          fontSize: 15,
                          fontWeight: FontWeight.w600,
                          letterSpacing: 0.6,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
