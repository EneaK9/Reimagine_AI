import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:provider/provider.dart';
import 'providers/chat_provider.dart';
import 'providers/auth_provider.dart';
import 'providers/scene_provider.dart';
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

class ReimagineAIApp extends StatelessWidget {
  const ReimagineAIApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
        ChangeNotifierProvider(create: (_) => SceneProvider()),
      ],
      child: MaterialApp(
        title: 'ReimagineAI',
        debugShowCheckedModeBanner: false,
        theme: AppTheme.lightTheme,
        // Landing page on web; mobile builds skip straight to auth.
        home: kIsWeb ? const LandingScreen() : const LoginScreen(),
      ),
    );
  }
}
