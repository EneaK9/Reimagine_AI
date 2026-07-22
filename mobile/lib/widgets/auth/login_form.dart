import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import '../../providers/auth_provider.dart';
import '../../screens/chat_screen.dart';
import '../../theme/app_theme.dart';
import 'auth_buttons.dart';
import 'auth_text_field.dart';

/// Login form column - used inside the animated auth screen.
class LoginForm extends StatefulWidget {
  const LoginForm({super.key, required this.onToggle});

  /// Called when the user taps "Sign Up" to switch to the signup form.
  final VoidCallback onToggle;

  @override
  State<LoginForm> createState() => _LoginFormState();
}

class _LoginFormState extends State<LoginForm> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  bool _rememberMe = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _login() async {
    if (!_formKey.currentState!.validate()) return;

    final authProvider = context.read<AuthProvider>();
    final success = await authProvider.login(
      _emailController.text.trim(),
      _passwordController.text,
    );

    if (success && mounted) {
      Navigator.pushReplacement(
        context,
        MaterialPageRoute(builder: (_) => const ChatScreen()),
      );
    }
  }

  void _showComingSoon(String feature) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('$feature coming soon!'),
        backgroundColor: AppTheme.ink,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Form(
      key: _formKey,
      child: AutofillGroup(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const AuthBrand(),
            const SizedBox(height: 72),
            Text(
              'Welcome Back',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSerifDisplay(
                fontSize: 40,
                color: AppTheme.ink,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              'Enter your email and password to access your account',
              textAlign: TextAlign.center,
              style: GoogleFonts.dmSans(
                fontSize: 13.5,
                color: AppTheme.authMuted,
              ),
            ),
            const SizedBox(height: 40),
            AuthTextField(
              label: 'Email',
              hint: 'Enter your email',
              controller: _emailController,
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
              autofillHints: const [AutofillHints.email],
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter your email';
                }
                if (!value.contains('@')) {
                  return 'Please enter a valid email';
                }
                return null;
              },
            ),
            const SizedBox(height: 22),
            AuthTextField(
              label: 'Password',
              hint: 'Enter your password',
              controller: _passwordController,
              obscurable: true,
              textInputAction: TextInputAction.done,
              autofillHints: const [AutofillHints.password],
              onSubmitted: (_) => _login(),
              validator: (value) {
                if (value == null || value.isEmpty) {
                  return 'Please enter your password';
                }
                if (value.length < 6) {
                  return 'Password must be at least 6 characters';
                }
                return null;
              },
            ),
            const SizedBox(height: 14),
            _buildRememberRow(),
            const SizedBox(height: 28),
            _buildSignInButton(),
            const SizedBox(height: 12),
            OutlinedAuthButton(
              label: 'Sign In with Google',
              leading: const GoogleGlyph(),
              onPressed: () => _showComingSoon('Google login'),
            ),
            const SizedBox(height: 64),
            _buildSignupLink(),
          ],
        ),
      ),
    );
  }

  Widget _buildRememberRow() {
    return Row(
      children: [
        SizedBox(
          width: 18,
          height: 18,
          child: Checkbox(
            value: _rememberMe,
            onChanged: (value) =>
                setState(() => _rememberMe = value ?? false),
            activeColor: AppTheme.primaryColor,
            side: const BorderSide(color: AppTheme.authBorder, width: 1.4),
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(4),
            ),
            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
        ),
        const SizedBox(width: 8),
        GestureDetector(
          onTap: () => setState(() => _rememberMe = !_rememberMe),
          child: Text(
            'Remember me',
            style: GoogleFonts.dmSans(
              fontSize: 13,
              color: AppTheme.authMuted,
            ),
          ),
        ),
        const Spacer(),
        TextButton(
          onPressed: () => _showComingSoon('Forgot password'),
          style: TextButton.styleFrom(
            padding: EdgeInsets.zero,
            minimumSize: Size.zero,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            overlayColor: Colors.transparent,
          ),
          child: Text(
            'Forgot Password',
            style: GoogleFonts.interTight(
              fontSize: 13,
              fontWeight: FontWeight.w600,
              color: AppTheme.primaryColor,
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildSignInButton() {
    return Consumer<AuthProvider>(
      builder: (context, auth, child) {
        if (auth.error != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(auth.error!),
                backgroundColor: AppTheme.error,
                behavior: SnackBarBehavior.floating,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
              ),
            );
            auth.clearError();
          });
        }

        return PrimaryAuthButton(
          label: 'Sign In',
          loading: auth.isLoading,
          onPressed: _login,
        );
      },
    );
  }

  Widget _buildSignupLink() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          "Don't have an account? ",
          style: GoogleFonts.dmSans(
            fontSize: 13.5,
            color: AppTheme.authMuted,
          ),
        ),
        TextButton(
          onPressed: widget.onToggle,
          style: TextButton.styleFrom(
            padding: EdgeInsets.zero,
            minimumSize: Size.zero,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
            overlayColor: Colors.transparent,
          ),
          child: Text(
            'Sign Up',
            style: GoogleFonts.interTight(
              fontSize: 13.5,
              fontWeight: FontWeight.w600,
              color: AppTheme.primaryColor,
            ),
          ),
        ),
      ],
    );
  }
}

/// Small brand lockup shown at the top of auth forms.
class AuthBrand extends StatelessWidget {
  const AuthBrand({super.key});

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        const Icon(Icons.home_rounded, size: 22, color: AppTheme.primaryColor),
        const SizedBox(width: 8),
        Text(
          'ReimagineAI',
          style: GoogleFonts.interTight(
            fontSize: 17,
            fontWeight: FontWeight.w700,
            color: AppTheme.ink,
          ),
        ),
      ],
    );
  }
}
