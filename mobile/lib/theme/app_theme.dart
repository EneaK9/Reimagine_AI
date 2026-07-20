import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

/// App Theme for ReimagineAI - LUXE greige / red-orange palette
class AppTheme {
  // Brand Colors - vivid red-orange accent
  static const Color primaryColor = Color(0xFFF2600C);
  static const Color primaryLight = Color(0xFFF97D3C);
  static const Color primaryDark = Color(0xFFD9530A);

  // Background Colors - warm greige
  static const Color background = Color(0xFFEFECE6);
  static const Color surface = Color(0xFFF4F2ED);
  static const Color cardColor = Color(0xFFF4F2ED);
  static const Color inputBackground = Color(0xFFE9E5DE);
  static const Color panelTone = Color(0xFFE7E3DC);
  static const Color secondaryButton = Color(0xFFD8D4CD);

  // Text Colors
  static const Color textPrimary = Color(0xFF1D1B18);
  static const Color textSecondary = Color(0xFF5C5A55);
  static const Color textMuted = Color(0xFF8A867E);
  static const Color textOnPrimary = Color(0xFFFFFFFF);

  // Accent Colors
  static const Color success = Color(0xFF22C55E);
  static const Color error = Color(0xFFEF4444);
  static const Color warning = Color(0xFFF59E0B);

  // Border Colors
  static const Color border = Color(0xFFDCD7CE);
  static const Color borderLight = Color(0xFFE7E3DC);

  // Auth palette - greige family
  static const Color ink = Color(0xFF1D1B18);
  static const Color authFieldFill = Color(0xFFE9E5DE);
  static const Color authBorder = Color(0xFFDCD7CE);
  static const Color authMuted = Color(0xFF8A867E);
  static const double authFieldRadius = 10;
  static const double authButtonRadius = 12;
  static const double authPanelRadius = 28;

  // Landing-only tokens
  static const Color gridLine = Color(0xFFDBD6CD);
  static const Color watermark = Color(0xFFCBC9C1);
  static const Color landingAlt = Color(0xFFE1DFD8);

  // Interaction overlays - neutral gray for hover/focus/press everywhere
  static const Color overlayBase = Color(0xFF8E8E93);
  static const Color hoverGray = Color(0x148E8E93); // ~8% gray
  static const Color pressGray = Color(0x1F8E8E93); // ~12% gray

  // Legacy dark colors (for compatibility during transition)
  static const Color cardDark = Color(0xFFF4F2ED);
  static const Color surfaceDark = Color(0xFFE9E5DE);
  static const Color backgroundDark = Color(0xFFEFECE6);

  // Gradients
  static const LinearGradient primaryGradient = LinearGradient(
    colors: [primaryColor, primaryLight],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  static const LinearGradient backgroundGradient = LinearGradient(
    colors: [background, Color(0xFFF4F2ED)],
    begin: Alignment.topCenter,
    end: Alignment.bottomCenter,
  );

  static const LinearGradient warmGradient = LinearGradient(
    colors: [Color(0xFFF4F2ED), Color(0xFFEFECE6)],
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
  );

  // Shadows
  static List<BoxShadow> cardShadow = [
    BoxShadow(
      color: Colors.black.withOpacity(0.04),
      blurRadius: 10,
      offset: const Offset(0, 2),
    ),
  ];
  
  static List<BoxShadow> elevatedShadow = [
    BoxShadow(
      color: Colors.black.withOpacity(0.08),
      blurRadius: 20,
      offset: const Offset(0, 4),
    ),
  ];

  /// Light Theme (Main Theme)
  static ThemeData lightTheme = ThemeData(
    useMaterial3: true,
    brightness: Brightness.light,
    scaffoldBackgroundColor: background,
    primaryColor: primaryColor,
    // Neutral gray interaction states (instead of tinted orange/yellow)
    hoverColor: hoverGray,
    focusColor: hoverGray,
    highlightColor: pressGray,
    splashColor: pressGray,
    colorScheme: const ColorScheme.light(
      primary: primaryColor,
      secondary: primaryLight,
      tertiary: success,
      surface: surface,
      onPrimary: Colors.white,
      onSecondary: Colors.white,
      onSurface: textPrimary,
    ),
    
    // App Bar
    appBarTheme: AppBarTheme(
      backgroundColor: Colors.transparent,
      elevation: 0,
      centerTitle: false,
      titleTextStyle: GoogleFonts.dmSerifDisplay(
        fontSize: 24,
        fontWeight: FontWeight.w500,
        color: textPrimary,
      ),
      iconTheme: const IconThemeData(color: textPrimary),
    ),
    
    // Card
    cardTheme: CardThemeData(
      color: cardColor,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(20),
      ),
    ),
    
    // Text - Using DM Serif Display for headings, DM Sans for body
    textTheme: TextTheme(
      displayLarge: GoogleFonts.dmSerifDisplay(
        fontSize: 48,
        fontWeight: FontWeight.w400,
        color: textPrimary,
      ),
      displayMedium: GoogleFonts.dmSerifDisplay(
        fontSize: 36,
        fontWeight: FontWeight.w400,
        color: textPrimary,
      ),
      displaySmall: GoogleFonts.dmSerifDisplay(
        fontSize: 28,
        fontWeight: FontWeight.w400,
        color: textPrimary,
      ),
      headlineLarge: GoogleFonts.dmSerifDisplay(
        fontSize: 24,
        fontWeight: FontWeight.w500,
        color: textPrimary,
      ),
      headlineMedium: GoogleFonts.dmSerifDisplay(
        fontSize: 20,
        fontWeight: FontWeight.w500,
        color: textPrimary,
      ),
      headlineSmall: GoogleFonts.dmSans(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      titleLarge: GoogleFonts.dmSans(
        fontSize: 18,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      titleMedium: GoogleFonts.dmSans(
        fontSize: 16,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      titleSmall: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      bodyLarge: GoogleFonts.dmSans(
        fontSize: 16,
        fontWeight: FontWeight.w400,
        color: textPrimary,
      ),
      bodyMedium: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w400,
        color: textSecondary,
      ),
      bodySmall: GoogleFonts.dmSans(
        fontSize: 12,
        fontWeight: FontWeight.w400,
        color: textMuted,
      ),
      labelLarge: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w600,
        color: textPrimary,
      ),
      labelMedium: GoogleFonts.dmSans(
        fontSize: 12,
        fontWeight: FontWeight.w500,
        color: textSecondary,
      ),
      labelSmall: GoogleFonts.dmSans(
        fontSize: 10,
        fontWeight: FontWeight.w500,
        color: textMuted,
      ),
    ),
    
    // Input Decoration
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: surface,
      hintStyle: GoogleFonts.dmSans(color: textMuted, fontSize: 15),
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: border),
      ),
      enabledBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: BorderSide(color: border),
      ),
      focusedBorder: OutlineInputBorder(
        borderRadius: BorderRadius.circular(16),
        borderSide: const BorderSide(color: primaryColor, width: 2),
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
    ),
    
    // Elevated Button
    elevatedButtonTheme: ElevatedButtonThemeData(
      style: ElevatedButton.styleFrom(
        backgroundColor: primaryColor,
        foregroundColor: Colors.white,
        overlayColor: overlayBase,
        elevation: 0,
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        textStyle: GoogleFonts.dmSans(
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
    
    // Outlined Button
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: primaryColor,
        overlayColor: overlayBase,
        side: const BorderSide(color: primaryColor, width: 1.5),
        padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 16),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
        ),
        textStyle: GoogleFonts.dmSans(
          fontSize: 16,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
    
    // Text Button
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(
        foregroundColor: primaryColor,
        overlayColor: overlayBase,
        textStyle: GoogleFonts.dmSans(
          fontSize: 14,
          fontWeight: FontWeight.w600,
        ),
      ),
    ),
    
    // Icon Button
    iconButtonTheme: IconButtonThemeData(
      style: IconButton.styleFrom(
        foregroundColor: textPrimary,
        overlayColor: overlayBase,
      ),
    ),
    
    // Bottom Navigation
    bottomNavigationBarTheme: const BottomNavigationBarThemeData(
      backgroundColor: surface,
      selectedItemColor: primaryColor,
      unselectedItemColor: textMuted,
    ),
    
    // Floating Action Button
    floatingActionButtonTheme: const FloatingActionButtonThemeData(
      backgroundColor: primaryColor,
      foregroundColor: Colors.white,
      elevation: 4,
    ),
    
    // Divider
    dividerTheme: DividerThemeData(
      color: border,
      thickness: 1,
    ),
    
    // Chip
    chipTheme: ChipThemeData(
      backgroundColor: inputBackground,
      selectedColor: primaryColor.withOpacity(0.15),
      labelStyle: GoogleFonts.dmSans(
        fontSize: 14,
        fontWeight: FontWeight.w500,
      ),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
      ),
    ),
    
    // Checkbox
    checkboxTheme: const CheckboxThemeData(
      overlayColor: WidgetStatePropertyAll(hoverGray),
    ),

    // Switch
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return Colors.white;
        return textMuted;
      }),
      trackColor: WidgetStateProperty.resolveWith((states) {
        if (states.contains(WidgetState.selected)) return primaryColor;
        return border;
      }),
    ),
  );
  
  // Keep darkTheme for backwards compatibility
  static ThemeData darkTheme = lightTheme;
}
