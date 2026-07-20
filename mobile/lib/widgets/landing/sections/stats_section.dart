import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../decorations.dart';
import '../landing_section.dart';

class StatsSection extends StatelessWidget {
  const StatsSection({super.key});

  static const _services = [
    (
      'AI Chat Design',
      'describe your dream room and get guided redesign suggestions in conversation',
      '120 Project'
    ),
    (
      'Photo Redesign',
      'upload a room photo and receive multiple AI-generated design variations',
      '96 Project'
    ),
    (
      '3D Room Scan',
      'turn a single photo into a navigable depth mesh of your space',
      '48 Project'
    ),
  ];

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
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 4, child: _serviceList()),
                    const SizedBox(width: 32),
                    Expanded(flex: 5, child: _highlightCard()),
                  ],
                )
              : Column(
                  children: [
                    _serviceList(),
                    const SizedBox(height: 32),
                    _highlightCard(),
                  ],
                ),
        ],
      ),
    );
  }

  Widget _serviceList() {
    return Column(
      children: [
        for (var i = 0; i < _services.length; i++) ...[
          if (i > 0)
            const Divider(height: 1, color: AppTheme.gridLine),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 28),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        _services[i].$1,
                        style: GoogleFonts.interTight(
                          fontSize: 20,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.ink,
                        ),
                      ),
                      const SizedBox(height: 8),
                      Text(
                        _services[i].$2,
                        style: GoogleFonts.interTight(
                          fontSize: 13,
                          height: 1.5,
                          color: AppTheme.textMuted,
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 16),
                Text(
                  _services[i].$3,
                  style: GoogleFonts.interTight(
                    fontSize: 14,
                    fontWeight: FontWeight.w500,
                    color: AppTheme.ink,
                  ),
                ),
              ],
            ),
          ),
        ],
      ],
    );
  }

  Widget _highlightCard() {
    return ClipPath(
      clipper: const NotchedCornerClipper(
        corner: NotchCorner.topLeft,
        notchSize: 64,
      ),
      child: Container(
        color: AppTheme.panelTone,
        padding: const EdgeInsets.fromLTRB(40, 48, 40, 40),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'We Are Your AI Interior Design Consultant',
              style: GoogleFonts.interTight(
                fontSize: 30,
                fontWeight: FontWeight.w700,
                height: 1.2,
                color: AppTheme.ink,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Experience in this field means we combine design taste with generative AI — so every redesign feels intentional, not random.',
              style: GoogleFonts.interTight(
                fontSize: 14,
                height: 1.55,
                color: AppTheme.textSecondary,
              ),
            ),
            const SizedBox(height: 40),
            Row(
              children: [
                Expanded(
                  child: _stat('4+', 'Design Variations'),
                ),
                Expanded(
                  child: _stat('60s+', 'Average Redesign'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _stat(String value, String label) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          value,
          style: GoogleFonts.interTight(
            fontSize: 42,
            fontWeight: FontWeight.w700,
            color: AppTheme.primaryColor,
            height: 1,
          ),
        ),
        const SizedBox(height: 8),
        Text(
          label,
          style: GoogleFonts.interTight(
            fontSize: 13,
            fontWeight: FontWeight.w500,
            color: AppTheme.ink,
          ),
        ),
      ],
    );
  }
}
