import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../decorations.dart';
import '../landing_section.dart';

class VisionSection extends StatelessWidget {
  const VisionSection({super.key});

  static const _cabinet = 'assets/images/landing/vision_cabinet.png';
  static const _pillA = 'assets/images/landing/hero_thumb_a.png';
  static const _pillB = 'assets/images/landing/hero_thumb_b.png';

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
                    Expanded(flex: 5, child: _headlineBlock()),
                    const SizedBox(width: 32),
                    Expanded(
                      flex: 5,
                      child: AspectRatio(
                        aspectRatio: 4 / 3,
                        child: NotchedImage(
                          asset: _cabinet,
                          corner: NotchCorner.bottomLeft,
                          notchSize: 64,
                          semanticLabel: 'Vision brought to life with AI',
                        ),
                      ),
                    ),
                  ],
                )
              : Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    _headlineBlock(),
                    const SizedBox(height: 28),
                    AspectRatio(
                      aspectRatio: 4 / 3,
                      child: NotchedImage(
                        asset: _cabinet,
                        corner: NotchCorner.bottomLeft,
                        notchSize: 48,
                        semanticLabel: 'Vision brought to life with AI',
                      ),
                    ),
                  ],
                ),
        ],
      ),
    );
  }

  Widget _headlineBlock() {
    final base = GoogleFonts.interTight(
      fontSize: 44,
      fontWeight: FontWeight.w700,
      height: 1.15,
      letterSpacing: -0.7,
      color: AppTheme.ink,
    );
    final italic = GoogleFonts.interTight(
      fontSize: 44,
      fontWeight: FontWeight.w600,
      fontStyle: FontStyle.italic,
      height: 1.15,
      letterSpacing: -0.7,
      color: AppTheme.ink,
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 10,
          runSpacing: 10,
          children: [
            Text('Bring Vision', style: base),
            _pillImage(_pillA),
            Text('to Life', style: italic),
            _pillImage(_pillB),
            Text('with AI', style: base),
            Container(
              width: 10,
              height: 10,
              color: AppTheme.primaryColor,
            ),
          ],
        ),
        const SizedBox(height: 40),
        Text(
          'Design Tools',
          style: GoogleFonts.interTight(
            fontSize: 18,
            fontWeight: FontWeight.w600,
            color: AppTheme.ink,
          ),
        ),
        const SizedBox(height: 12),
        RichText(
          text: TextSpan(
            style: GoogleFonts.interTight(
              fontSize: 14,
              height: 1.6,
              color: AppTheme.textSecondary,
            ),
            children: [
              TextSpan(
                text: 'Gain ',
                style: GoogleFonts.interTight(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.primaryColor,
                ),
              ),
              const TextSpan(
                text:
                    'insight into your space with chat, photo analysis, and 3D mesh tools — all in one place.',
              ),
            ],
          ),
        ),
      ],
    );
  }

  Widget _pillImage(String asset) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Image.asset(
        asset,
        width: 64,
        height: 32,
        fit: BoxFit.cover,
      ),
    );
  }
}
