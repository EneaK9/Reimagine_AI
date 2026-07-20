import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../circle_arrow_button.dart';
import '../decorations.dart';
import '../landing_section.dart';

class ServicesHeading extends StatelessWidget {
  const ServicesHeading({super.key, required this.onScrollDown});

  final VoidCallback onScrollDown;

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 800;

    return LandingSection(
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: const GridLinesPainter(
                columnCount: 4,
                rowCount: 1,
                showCrosshairs: true,
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 40),
            child: wide
                ? Row(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Expanded(
                        flex: 3,
                        child: Text(
                          'Our AI Design Services Tailored Uniquely For You.',
                          style: GoogleFonts.interTight(
                            fontSize: 40,
                            fontWeight: FontWeight.w700,
                            height: 1.15,
                            letterSpacing: -0.6,
                            color: AppTheme.ink,
                          ),
                        ),
                      ),
                      const SizedBox(width: 32),
                      Expanded(
                        flex: 2,
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.end,
                          children: [
                            CircleArrowButton(
                              direction: AxisDirection.down,
                              onPressed: onScrollDown,
                            ),
                            const SizedBox(height: 24),
                            Text(
                              'Time to update and breathe fresh life into your existing home? Bathroom or kitchen in need of a refresh? We\'re here to provide you with a quality AI redesign.',
                              textAlign: TextAlign.right,
                              style: GoogleFonts.interTight(
                                fontSize: 14,
                                height: 1.55,
                                color: AppTheme.textSecondary,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  )
                : Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Our AI Design Services Tailored Uniquely For You.',
                        style: GoogleFonts.interTight(
                          fontSize: 32,
                          fontWeight: FontWeight.w700,
                          height: 1.15,
                          color: AppTheme.ink,
                        ),
                      ),
                      const SizedBox(height: 20),
                      Text(
                        'Time to update and breathe fresh life into your existing home? Bathroom or kitchen in need of a refresh? We\'re here to provide you with a quality AI redesign.',
                        style: GoogleFonts.interTight(
                          fontSize: 14,
                          height: 1.55,
                          color: AppTheme.textSecondary,
                        ),
                      ),
                      const SizedBox(height: 20),
                      CircleArrowButton(
                        direction: AxisDirection.down,
                        onPressed: onScrollDown,
                      ),
                    ],
                  ),
          ),
        ],
      ),
    );
  }
}
