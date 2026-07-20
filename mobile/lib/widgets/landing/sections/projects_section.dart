import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../../theme/app_theme.dart';
import '../circle_arrow_button.dart';
import '../landing_section.dart';

class ProjectsSection extends StatelessWidget {
  const ProjectsSection({super.key, required this.onDetail});

  final VoidCallback onDetail;

  static const _large = 'assets/images/landing/project_large.png';
  static const _mid = 'assets/images/landing/project_mid.png';
  static const _right = 'assets/images/landing/project_right.png';

  @override
  Widget build(BuildContext context) {
    final wide = MediaQuery.sizeOf(context).width >= 900;

    return LandingSection(
      child: wide
          ? Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(
                  flex: 2,
                  child: _LargeCard(onDetail: onDetail),
                ),
                const SizedBox(width: 24),
                Expanded(
                  child: _TallCard(
                    image: _mid,
                    title: 'Property Interior',
                    onTap: onDetail,
                  ),
                ),
                const SizedBox(width: 24),
                Expanded(
                  child: _TallCard(
                    image: _right,
                    title: 'Building Architect',
                    onTap: onDetail,
                  ),
                ),
              ],
            )
          : Column(
              children: [
                _LargeCard(onDetail: onDetail),
                const SizedBox(height: 24),
                _TallCard(
                  image: _mid,
                  title: 'Property Interior',
                  onTap: onDetail,
                ),
                const SizedBox(height: 24),
                _TallCard(
                  image: _right,
                  title: 'Building Architect',
                  onTap: onDetail,
                ),
              ],
            ),
    );
  }
}

class _LargeCard extends StatelessWidget {
  const _LargeCard({required this.onDetail});

  final VoidCallback onDetail;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AspectRatio(
          aspectRatio: 4 / 3,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: Image.asset(
              ProjectsSection._large,
              fit: BoxFit.cover,
              semanticLabel: 'Recent interior design project',
            ),
          ),
        ),
        const SizedBox(height: 20),
        Text(
          'Our Recent Design Interior Project',
          style: GoogleFonts.interTight(
            fontSize: 26,
            fontWeight: FontWeight.w700,
            color: AppTheme.ink,
            height: 1.2,
          ),
        ),
        const SizedBox(height: 10),
        Text(
          'Get a powerful custom redesign mixed just for you — soft, stylish AI-generated rooms from a single photo.',
          style: GoogleFonts.interTight(
            fontSize: 14,
            height: 1.5,
            color: AppTheme.textSecondary,
          ),
        ),
        const SizedBox(height: 18),
        _DetailPill(onTap: onDetail),
      ],
    );
  }
}

class _TallCard extends StatelessWidget {
  const _TallCard({
    required this.image,
    required this.title,
    required this.onTap,
  });

  final String image;
  final String title;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AspectRatio(
          aspectRatio: 3 / 4,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(2),
            child: Image.asset(
              image,
              fit: BoxFit.cover,
              semanticLabel: title,
            ),
          ),
        ),
        const SizedBox(height: 18),
        Text(
          title,
          style: GoogleFonts.interTight(
            fontSize: 22,
            fontWeight: FontWeight.w700,
            color: AppTheme.ink,
          ),
        ),
        const SizedBox(height: 14),
        CircleArrowButton(onPressed: onTap, size: 44),
      ],
    );
  }
}

class _DetailPill extends StatefulWidget {
  const _DetailPill({required this.onTap});

  final VoidCallback onTap;

  @override
  State<_DetailPill> createState() => _DetailPillState();
}

class _DetailPillState extends State<_DetailPill> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 150),
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            border: Border.all(color: AppTheme.ink, width: 1.2),
            color: _hovered ? AppTheme.ink : Colors.transparent,
          ),
          child: Text(
            'Detail Project',
            style: GoogleFonts.interTight(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: _hovered ? AppTheme.background : AppTheme.ink,
            ),
          ),
        ),
      ),
    );
  }
}
