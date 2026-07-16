import 'package:flutter/material.dart';
import '../widgets/auth/auth_art_panel.dart';
import '../widgets/auth/login_form.dart';
import '../widgets/auth/signup_form.dart';

/// Auth screen hosting both login and signup.
///
/// On wide screens the artwork panel slides between the left (login) and
/// right (signup) halves while the forms cross-fade on the opposite side.
/// On narrow screens the forms simply transition in place.
class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  static const double _artBreakpoint = 900;
  static const Duration _slideDuration = Duration(milliseconds: 650);
  static const Curve _slideCurve = Curves.easeInOutCubic;

  bool _isSignup = false;

  void _toggle() => setState(() => _isSignup = !_isSignup);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: LayoutBuilder(
        builder: (context, constraints) {
          final wide = constraints.maxWidth >= _artBreakpoint;
          return wide
              ? _buildWideLayout(constraints)
              : _buildNarrowLayout();
        },
      ),
    );
  }

  // ---------- Narrow: forms swap in place ----------

  Widget _buildNarrowLayout() {
    return SafeArea(
      child: AnimatedSwitcher(
        duration: const Duration(milliseconds: 350),
        switchInCurve: Curves.easeOutCubic,
        switchOutCurve: Curves.easeInCubic,
        transitionBuilder: (child, animation) => FadeTransition(
          opacity: animation,
          child: SlideTransition(
            position: Tween<Offset>(
              begin: const Offset(0, 0.03),
              end: Offset.zero,
            ).animate(animation),
            child: child,
          ),
        ),
        child: Center(
          key: ValueKey(_isSignup),
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: _isSignup
                  ? SignupForm(onToggle: _toggle)
                  : LoginForm(onToggle: _toggle),
            ),
          ),
        ),
      ),
    );
  }

  // ---------- Wide: sliding art panel over swapping forms ----------

  Widget _buildWideLayout(BoxConstraints constraints) {
    final halfWidth = constraints.maxWidth / 2;

    return Stack(
      children: [
        // Login form lives in the right half.
        Positioned(
          left: halfWidth,
          top: 0,
          bottom: 0,
          width: halfWidth,
          child: _buildFormHalf(
            visible: !_isSignup,
            child: LoginForm(onToggle: _toggle),
          ),
        ),
        // Signup form lives in the left half.
        Positioned(
          left: 0,
          top: 0,
          bottom: 0,
          width: halfWidth,
          child: _buildFormHalf(
            visible: _isSignup,
            child: SignupForm(onToggle: _toggle),
          ),
        ),
        // Artwork panel slides across the top of the forms.
        AnimatedPositioned(
          duration: _slideDuration,
          curve: _slideCurve,
          left: _isSignup ? halfWidth : 0,
          top: 0,
          bottom: 0,
          width: halfWidth,
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: AnimatedSwitcher(
              duration: _slideDuration,
              child: _isSignup
                  ? const AuthArtPanel(
                      key: ValueKey('signup-art'),
                      quote: 'Design\nThe Space\nYou Love',
                      caption:
                          'Every great room starts with a single idea.\n'
                          'Bring yours to life with the help of AI.',
                    )
                  : const AuthArtPanel(
                      key: ValueKey('login-art'),
                      quote: 'Get\nEverything\nYou Want',
                      caption:
                          'You can get everything you want if you work hard,\n'
                          'trust the process, and stick to the plan.',
                    ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildFormHalf({required bool visible, required Widget child}) {
    return IgnorePointer(
      ignoring: !visible,
      child: AnimatedOpacity(
        duration: _slideDuration,
        curve: _slideCurve,
        opacity: visible ? 1 : 0,
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.symmetric(horizontal: 48, vertical: 32),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 400),
              child: child,
            ),
          ),
        ),
      ),
    );
  }
}
