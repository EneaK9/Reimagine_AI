import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../circle_arrow_button.dart';
import '../decorations.dart';
import '../landing_section.dart';

class FeatureSection extends StatelessWidget {
  const FeatureSection({super.key, required this.onNext});

  final VoidCallback onNext;

  static const _image = 'assets/images/landing/feature_split.png';

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;

    return LandingSection(
      child: Stack(
        children: [
          Positioned.fill(
            child: CustomPaint(
              painter: const GridLinesPainter(
                columnCount: 4,
                rowCount: 2,
                showCrosshairs: true,
              ),
            ),
          ),
          wide
              ? Row(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Expanded(
                      flex: 5,
                      child: AspectRatio(
                        aspectRatio: 4 / 3,
                        child: NotchedImage(
                          asset: _image,
                          corner: NotchCorner.topRight,
                          notchSize: 64,
                          semanticLabel: 'Comfortable redesigned living room',
                        ),
                      ),
                    ),
                    const SizedBox(width: 40),
                    Expanded(
                      flex: 4,
                      child: _copy(context),
                    ),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    AspectRatio(
                      aspectRatio: 4 / 3,
                      child: NotchedImage(
                        asset: _image,
                        corner: NotchCorner.topRight,
                        notchSize: 48,
                        semanticLabel: 'Comfortable redesigned living room',
                      ),
                    ),
                    const SizedBox(height: 28),
                    _copy(context),
                  ],
                ),
        ],
      ),
    );
  }

  Widget _copy(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Text(
                'Build A Comfortable Room By Using Our AI',
                style: GoogleFonts.interTight(
                  fontSize: 36,
                  fontWeight: FontWeight.w700,
                  height: 1.15,
                  letterSpacing: -0.5,
                  color: AppTheme.ink,
                ),
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '+',
              style: GoogleFonts.interTight(
                fontSize: 28,
                color: AppTheme.textMuted,
              ),
            ),
          ],
        ),
        const SizedBox(height: 32),
        Align(
          alignment: Alignment.centerRight,
          child: CircleArrowButton(onPressed: onNext),
        ),
      ],
    );
  }
}
