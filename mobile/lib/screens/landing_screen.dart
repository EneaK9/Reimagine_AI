import 'package:flutter/material.dart';
import '../theme/app_theme.dart';
import '../widgets/landing/sections/feature_section.dart';
import '../widgets/landing/sections/footer_cta.dart';
import '../widgets/landing/sections/hero_section.dart';
import '../widgets/landing/sections/landing_nav.dart';
import '../widgets/landing/sections/logos_strip.dart';
import '../widgets/landing/sections/projects_section.dart';
import '../widgets/landing/sections/services_heading.dart';
import '../widgets/landing/sections/stats_section.dart';
import '../widgets/landing/sections/vision_section.dart';
import 'login_screen.dart';

/// Marketing landing page — LUXE-style layout adapted for ReimagineAI.
class LandingScreen extends StatefulWidget {
  const LandingScreen({super.key});

  @override
  State<LandingScreen> createState() => _LandingScreenState();
}

class _LandingScreenState extends State<LandingScreen> {
  final _scrollController = ScrollController();

  final _topKey = GlobalKey();
  final _aboutKey = GlobalKey();
  final _servicesKey = GlobalKey();
  final _galleryKey = GlobalKey();
  final _featuresKey = GlobalKey();
  final _visionKey = GlobalKey();
  final _footerKey = GlobalKey();

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _goToLogin() {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
    );
  }

  Future<void> _scrollTo(GlobalKey key) async {
    final ctx = key.currentContext;
    if (ctx == null) return;
    await Scrollable.ensureVisible(
      ctx,
      duration: const Duration(milliseconds: 650),
      curve: Curves.easeInOutCubic,
      alignment: 0.05,
    );
  }

  void _onNavigate(String anchor) {
    switch (anchor) {
      case 'top':
        _scrollTo(_topKey);
      case 'about':
        _scrollTo(_aboutKey);
      case 'services':
        _scrollTo(_servicesKey);
      case 'gallery':
        _scrollTo(_galleryKey);
      case 'features':
        _scrollTo(_featuresKey);
      default:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: CustomScrollView(
        controller: _scrollController,
        slivers: [
          // Sticky-feeling top bar (scrolls with content but sits first)
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _topKey,
              child: LandingNav(
                onNavigate: _onNavigate,
                onCta: _goToLogin,
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _aboutKey,
              child: HeroSection(
                onTryApp: _goToLogin,
                onLearnMore: () => _scrollTo(_servicesKey),
              ),
            ),
          ),
          const SliverToBoxAdapter(child: LogosStrip()),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _servicesKey,
              child: ServicesHeading(
                onScrollDown: () => _scrollTo(_galleryKey),
              ),
            ),
          ),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _galleryKey,
              child: ProjectsSection(onDetail: _goToLogin),
            ),
          ),
          const SliverToBoxAdapter(child: StatsSection()),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _featuresKey,
              child: FeatureSection(onNext: () => _scrollTo(_visionKey)),
            ),
          ),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _visionKey,
              child: const VisionSection(),
            ),
          ),
          SliverToBoxAdapter(
            child: KeyedSubtree(
              key: _footerKey,
              child: FooterCta(onCollaborate: _goToLogin),
            ),
          ),
        ],
      ),
    );
  }
}
