import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../circle_arrow_button.dart';
import '../decorations.dart';
import '../landing_button.dart';
import '../landing_section.dart';

class HeroSection extends StatelessWidget {
  const HeroSection({
    super.key,
    required this.onTryApp,
    required this.onLearnMore,
  });

  final VoidCallback onTryApp;
  final VoidCallback onLearnMore;

  static const _heroMain = 'assets/images/landing/hero_main.png';
  static const _thumbA = 'assets/images/landing/hero_thumb_a.png';
  static const _thumbB = 'assets/images/landing/hero_thumb_b.png';

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
          wide ? _buildWide() : _buildNarrow(),
        ],
      ),
    );
  }

  Widget _buildWide() {
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            flex: 5,
            child: Padding(
              padding: const EdgeInsets.only(right: 32, top: 24, bottom: 24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  _headline(),
                  const SizedBox(height: 20),
                  Text(
                    'Collaborating with AI from concept to completion, delivering memorable room redesigns from a single photo or chat.',
                    style: GoogleFonts.interTight(
                      fontSize: 15,
                      height: 1.55,
                      color: AppTheme.textSecondary,
                    ),
                  ),
                  const SizedBox(height: 28),
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: [
                      LandingButton(
                        label: 'Try ReimagineAI',
                        onPressed: onTryApp,
                      ),
                      LandingButton(
                        label: 'Learn More',
                        variant: LandingButtonVariant.secondary,
                        onPressed: onLearnMore,
                      ),
                    ],
                  ),
                  const Spacer(),
                  const SizedBox(height: 32),
                  Row(
                    children: [
                      Expanded(child: _thumb(_thumbA, 'Interior detail')),
                      const SizedBox(width: 12),
                      Expanded(child: _thumb(_thumbB, 'Seating detail')),
                    ],
                  ),
                ],
              ),
            ),
          ),
          Expanded(
            flex: 5,
            child: SizedBox(
              height: 520,
              child: NotchedImage(
                asset: _heroMain,
                corner: NotchCorner.topLeft,
                notchSize: 72,
                semanticLabel: 'Featured redesigned living room',
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNarrow() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _headline(),
        const SizedBox(height: 16),
        Text(
          'Collaborating with AI from concept to completion, delivering memorable room redesigns from a single photo or chat.',
          style: GoogleFonts.interTight(
            fontSize: 15,
            height: 1.55,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 24),
        Wrap(
          spacing: 12,
          runSpacing: 12,
          children: [
            LandingButton(label: 'Try ReimagineAI', onPressed: onTryApp),
            LandingButton(
              label: 'Learn More',
              variant: LandingButtonVariant.secondary,
              onPressed: onLearnMore,
            ),
          ],
        ),
        const SizedBox(height: 28),
        AspectRatio(
          aspectRatio: 3 / 4,
          child: NotchedImage(
            asset: _heroMain,
            corner: NotchCorner.topLeft,
            notchSize: 48,
            semanticLabel: 'Featured redesigned living room',
          ),
        ),
        const SizedBox(height: 12),
        Row(
          children: [
            Expanded(child: _thumb(_thumbA, 'Interior detail')),
            const SizedBox(width: 12),
            Expanded(child: _thumb(_thumbB, 'Seating detail')),
          ],
        ),
        const SizedBox(height: 20),
        CircleArrowButton(
          direction: AxisDirection.down,
          onPressed: onLearnMore,
        ),
      ],
    );
  }

  Widget _headline() {
    final base = GoogleFonts.interTight(
      fontSize: 48,
      fontWeight: FontWeight.w700,
      height: 1.1,
      color: AppTheme.ink,
      letterSpacing: -0.8,
    );
    final italic = GoogleFonts.interTight(
      fontSize: 48,
      fontWeight: FontWeight.w600,
      fontStyle: FontStyle.italic,
      height: 1.1,
      color: AppTheme.ink,
      letterSpacing: -0.8,
    );

    return Wrap(
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        Text('Intelligently ', style: base),
        Text('Reimagined Home ', style: italic),
        Text('Design', style: base),
        const SizedBox(width: 10),
        const OrangeStarburst(size: 26),
      ],
    );
  }

  Widget _thumb(String asset, String label) {
    return AspectRatio(
      aspectRatio: 1,
      child: ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: Image.asset(asset, fit: BoxFit.cover, semanticLabel: label),
      ),
    );
  }
}
