import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../theme/app_theme.dart';

/// Decorative artwork panel shown beside auth forms on wide screens.
/// Uses brand greige / ink / orange — same system as the rest of the app.
class AuthArtPanel extends StatelessWidget {
  const AuthArtPanel({
    super.key,
    required this.quote,
    this.caption,
    this.eyebrow = 'REIMAGINE YOUR SPACE',
    this.imageAsset = 'assets/images/login_art.png',
    this.alignEnd = false,
  });

  final String quote;
  final String? caption;
  final String eyebrow;
  final String imageAsset;

  /// When true (signup / panel on the right), type aligns to the trailing edge.
  final bool alignEnd;

  @override
  Widget build(BuildContext context) {
    final cross = alignEnd ? CrossAxisAlignment.end : CrossAxisAlignment.start;
    final textAlign = alignEnd ? TextAlign.right : TextAlign.left;
    final lineColors = alignEnd
        ? [
            Colors.transparent,
            Colors.white.withValues(alpha: 0.35),
            AppTheme.primaryColor,
          ]
        : [
            AppTheme.primaryColor,
            Colors.white.withValues(alpha: 0.35),
            Colors.transparent,
          ];

    return ClipRRect(
      borderRadius: BorderRadius.circular(AppTheme.authPanelRadius),
      child: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset(
            imageAsset,
            fit: BoxFit.cover,
            errorBuilder: (_, __, ___) => const ColoredBox(
              color: AppTheme.ink,
            ),
          ),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [
                  Color(0x661D1B18),
                  Color(0x141D1B18),
                  Color(0xB31D1B18),
                ],
                stops: [0.0, 0.4, 1.0],
              ),
            ),
          ),
          DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: alignEnd ? Alignment.bottomRight : Alignment.bottomLeft,
                end: alignEnd ? Alignment.centerLeft : Alignment.centerRight,
                colors: const [
                  Color(0x33F2600C),
                  Color(0x00F2600C),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.fromLTRB(36, 36, 36, 40),
            child: Column(
              crossAxisAlignment: cross,
              children: [
                Row(
                  children: [
                    if (alignEnd)
                      Expanded(
                        child: Container(
                          height: 1.5,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(colors: lineColors),
                          ),
                        ),
                      ),
                    if (alignEnd) const SizedBox(width: 14),
                    Text(
                      eyebrow,
                      style: GoogleFonts.interTight(
                        color: Colors.white,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                        letterSpacing: 2.4,
                      ),
                    ),
                    if (!alignEnd) const SizedBox(width: 14),
                    if (!alignEnd)
                      Expanded(
                        child: Container(
                          height: 1.5,
                          decoration: BoxDecoration(
                            gradient: LinearGradient(colors: lineColors),
                          ),
                        ),
                      ),
                  ],
                ),
                const Spacer(),
                Text(
                  quote,
                  textAlign: textAlign,
                  style: GoogleFonts.dmSerifDisplay(
                    color: Colors.white,
                    fontSize: 48,
                    height: 1.1,
                    fontWeight: FontWeight.w400,
                  ),
                ),
                if (caption != null) ...[
                  const SizedBox(height: 18),
                  Text(
                    caption!,
                    textAlign: textAlign,
                    style: GoogleFonts.interTight(
                      color: Colors.white.withValues(alpha: 0.88),
                      fontSize: 14,
                      height: 1.55,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ],
      ),
    );
  }
}
