import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'providers/chat_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/scene_provider.dart';
import 'screens/chat_screen.dart';
import 'screens/landing_screen.dart';
import 'screens/login_screen.dart';
import 'theme/app_theme.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Set system UI overlay style for light theme
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.transparent,
      statusBarIconBrightness: Brightness.dark,
      systemNavigationBarColor: AppTheme.surface,
      systemNavigationBarIconBrightness: Brightness.dark,
    ),
  );

  runApp(const ReimagineAIApp());
}

/// Root navigator, used to return to sign-in when the session expires.
final GlobalKey<NavigatorState> _navigatorKey = GlobalKey<NavigatorState>();

class ReimagineAIApp extends StatelessWidget {
  const ReimagineAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        // Created eagerly so the saved session is restored at startup.
        ChangeNotifierProvider(
          create: (_) => AuthProvider()..initialize(),
          lazy: false,
        ),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
        ChangeNotifierProvider(create: (_) => SceneProvider()),
      ],
      child: _SessionExpiryListener(
        child: MaterialApp(
          navigatorKey: _navigatorKey,
          title: 'ReimagineAI',
          debugShowCheckedModeBanner: false,
          theme: AppTheme.lightTheme,
          home: const _StartScreen(),
        ),
      ),
    );
  }
}

/// First screen, picked once the saved session has been restored: the
/// landing page on web; on mobile the studio when signed in, else sign-in.
class _StartScreen extends StatefulWidget {
  const _StartScreen();

  @override
  State<_StartScreen> createState() => _StartScreenState();
}

class _StartScreenState extends State<_StartScreen> {
  Widget? _screen;

  @override
  Widget build(BuildContext context) {
    final auth = context.watch<AuthProvider>();
    if (!auth.isInitialized) return const _SplashScreen();
    // Decided once: signing in/out later navigates on its own, and an
    // expired session is handled by _SessionExpiryListener.
    return _screen ??= kIsWeb
        ? const LandingScreen()
        : auth.isLoggedIn
            ? const ChatScreen()
            : const LoginScreen();
  }
}

class _SplashScreen extends StatelessWidget {
  const _SplashScreen();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              'ReimagineAI',
              style: GoogleFonts.interTight(
                fontSize: 22,
                fontWeight: FontWeight.w700,
                color: AppTheme.ink,
              ),
            ),
            const SizedBox(height: 20),
            const SizedBox(
              width: 22,
              height: 22,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                color: AppTheme.primaryColor,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Sends the user back to sign-in when the backend rejects the saved token
/// (e.g. it expired or was replaced by a login on another device).
class _SessionExpiryListener extends StatefulWidget {
  const _SessionExpiryListener({required this.child});

  final Widget child;

  @override
  State<_SessionExpiryListener> createState() => _SessionExpiryListenerState();
}

class _SessionExpiryListenerState extends State<_SessionExpiryListener> {
  late final AuthProvider _auth;

  @override
  void initState() {
    super.initState();
    _auth = context.read<AuthProvider>()..addListener(_onAuthChanged);
  }

  @override
  void dispose() {
    _auth.removeListener(_onAuthChanged);
    super.dispose();
  }

  void _onAuthChanged() {
    if (!_auth.consumeSessionExpired()) return;
    final navigator = _navigatorKey.currentState;
    if (navigator == null) return;
    navigator.pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (_) => false,
    );
    ScaffoldMessenger.maybeOf(navigator.context)?.showSnackBar(
      const SnackBar(
        content: Text('Your session has expired. Please sign in again.'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
