import 'package:flutter/material.dart';

class AppTheme {
  static const Color primaryColor = Color(0xFF00FFCC); // Neon cyan
  static const Color backgroundColor = Color(0xFF0F172A); // Slate 900
  static const Color surfaceColor = Color(0xFF1E293B); // Slate 800
  static const Color textPrimaryColor = Colors.white;
  static const Color textSecondaryColor = Color(0xFF94A3B8); // Slate 400
  static const Color errorColor = Color(0xFFFF453A); // Neon Red

  static ThemeData get darkTheme {
    return ThemeData(
      brightness: Brightness.dark,
      scaffoldBackgroundColor: backgroundColor,
      primaryColor: primaryColor,
      colorScheme: const ColorScheme.dark(
        primary: primaryColor,
        surface: surfaceColor,
        error: errorColor,
      ),
      fontFamily: 'Inter', // Assuming Inter or system default, we'll use system default if not loaded
      textTheme: const TextTheme(
        displayLarge: TextStyle(color: textPrimaryColor, fontSize: 32, fontWeight: FontWeight.bold),
        titleLarge: TextStyle(color: textPrimaryColor, fontSize: 24, fontWeight: FontWeight.w600),
        bodyLarge: TextStyle(color: textPrimaryColor, fontSize: 16),
        bodyMedium: TextStyle(color: textSecondaryColor, fontSize: 14),
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        iconTheme: IconThemeData(color: textPrimaryColor),
        titleTextStyle: TextStyle(color: textPrimaryColor, fontSize: 20, fontWeight: FontWeight.w600),
      ),
    );
  }
}
