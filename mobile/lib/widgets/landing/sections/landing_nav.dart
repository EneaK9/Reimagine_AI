import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../decorations.dart';
import '../landing_section.dart';

class LandingNav extends StatelessWidget {
  const LandingNav({
    super.key,
    required this.onNavigate,
    required this.onCta,
  });

  final void Function(String anchor) onNavigate;
  final VoidCallback onCta;

  static const _links = [
    ('About', 'about'),
    ('Services', 'services'),
    ('Gallery', 'gallery'),
    ('Features', 'features'),
  ];

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 700;

    return LandingSection(
      padding: EdgeInsets.symmetric(
        horizontal: wide ? 48 : 20,
        vertical: 20,
      ),
      child: Row(
        children: [
          MouseRegion(
            cursor: SystemMouseCursors.click,
            child: GestureDetector(
              onTap: () => onNavigate('top'),
              child: const LandingWordmark(),
            ),
          ),
          if (wide) ...[
            const Spacer(),
            for (final (label, id) in _links)
              _NavLink(label: label, onTap: () => onNavigate(id)),
            const Spacer(),
            IconButton(
              onPressed: onCta,
              icon: const Icon(Icons.menu_rounded),
              color: AppTheme.ink,
              tooltip: 'Open app',
            ),
          ] else ...[
            const Spacer(),
            PopupMenuButton<String>(
              icon: const Icon(Icons.menu_rounded, color: AppTheme.ink),
              color: AppTheme.surface,
              onSelected: (value) {
                if (value == 'cta') {
                  onCta();
                } else {
                  onNavigate(value);
                }
              },
              itemBuilder: (_) => [
                for (final (label, id) in _links)
                  PopupMenuItem(value: id, child: Text(label)),
                const PopupMenuItem(
                  value: 'cta',
                  child: Text('Try ReimagineAI'),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

class _NavLink extends StatefulWidget {
  const _NavLink({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  State<_NavLink> createState() => _NavLinkState();
}

class _NavLinkState extends State<_NavLink> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: MouseRegion(
        cursor: SystemMouseCursors.click,
        onEnter: (_) => setState(() => _hovered = true),
        onExit: (_) => setState(() => _hovered = false),
        child: GestureDetector(
          onTap: widget.onTap,
          child: AnimatedDefaultTextStyle(
            duration: const Duration(milliseconds: 150),
            style: GoogleFonts.interTight(
              fontSize: 14,
              fontWeight: FontWeight.w500,
              color: AppTheme.ink,
              decoration:
                  _hovered ? TextDecoration.underline : TextDecoration.none,
              decorationColor: AppTheme.ink,
            ),
            child: Text(widget.label),
          ),
        ),
      ),
    );
  }
}
