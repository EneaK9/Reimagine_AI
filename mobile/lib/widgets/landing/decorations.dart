import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import '../../theme/app_theme.dart';

/// Thin hairline grid with optional crosshair "+" marks at intersections.
class GridLinesPainter extends CustomPainter {
  const GridLinesPainter({
    this.columnCount = 4,
    this.rowCount = 0,
    this.showCrosshairs = true,
    this.color = AppTheme.gridLine,
  });

  final int columnCount;
  final int rowCount;
  final bool showCrosshairs;
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 1
      ..style = PaintingStyle.stroke;

    if (columnCount > 0) {
      final step = size.width / columnCount;
      for (var i = 0; i <= columnCount; i++) {
        final x = i * step;
        canvas.drawLine(Offset(x, 0), Offset(x, size.height), paint);
      }
    }

    if (rowCount > 0) {
      final step = size.height / rowCount;
      for (var i = 0; i <= rowCount; i++) {
        final y = i * step;
        canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
      }
    }

    if (showCrosshairs && columnCount > 0) {
      final colStep = size.width / columnCount;
      final rowStep = rowCount > 0 ? size.height / rowCount : size.height;
      final rows = rowCount > 0 ? rowCount : 1;
      final crossPaint = Paint()
        ..color = color
        ..strokeWidth = 1.2
        ..strokeCap = StrokeCap.round;

      for (var c = 0; c <= columnCount; c++) {
        for (var r = 0; r <= rows; r++) {
          final cx = c * colStep;
          final cy = r * rowStep;
          const arm = 5.0;
          canvas.drawLine(
            Offset(cx - arm, cy),
            Offset(cx + arm, cy),
            crossPaint,
          );
          canvas.drawLine(
            Offset(cx, cy - arm),
            Offset(cx, cy + arm),
            crossPaint,
          );
        }
      }
    }
  }

  @override
  bool shouldRepaint(covariant GridLinesPainter oldDelegate) =>
      oldDelegate.columnCount != columnCount ||
      oldDelegate.rowCount != rowCount ||
      oldDelegate.showCrosshairs != showCrosshairs ||
      oldDelegate.color != color;
}

/// Cuts one corner of a rectangle at a 45° angle (LUXE notched image look).
enum NotchCorner { topLeft, topRight, bottomLeft, bottomRight }

class NotchedCornerClipper extends CustomClipper<Path> {
  const NotchedCornerClipper({
    this.corner = NotchCorner.topLeft,
    this.notchSize = 56,
  });

  final NotchCorner corner;
  final double notchSize;

  @override
  Path getClip(Size size) {
    final n = notchSize.clamp(0.0, size.shortestSide / 2);
    final path = Path();

    switch (corner) {
      case NotchCorner.topLeft:
        path
          ..moveTo(n, 0)
          ..lineTo(size.width, 0)
          ..lineTo(size.width, size.height)
          ..lineTo(0, size.height)
          ..lineTo(0, n)
          ..close();
      case NotchCorner.topRight:
        path
          ..moveTo(0, 0)
          ..lineTo(size.width - n, 0)
          ..lineTo(size.width, n)
          ..lineTo(size.width, size.height)
          ..lineTo(0, size.height)
          ..close();
      case NotchCorner.bottomLeft:
        path
          ..moveTo(0, 0)
          ..lineTo(size.width, 0)
          ..lineTo(size.width, size.height)
          ..lineTo(n, size.height)
          ..lineTo(0, size.height - n)
          ..close();
      case NotchCorner.bottomRight:
        path
          ..moveTo(0, 0)
          ..lineTo(size.width, 0)
          ..lineTo(size.width, size.height - n)
          ..lineTo(size.width - n, size.height)
          ..lineTo(0, size.height)
          ..close();
    }
    return path;
  }

  @override
  bool shouldReclip(covariant NotchedCornerClipper oldClipper) =>
      oldClipper.corner != corner || oldClipper.notchSize != notchSize;
}

/// Eight-pointed asterisk mark used as the brand logo.
class AsteriskMark extends StatelessWidget {
  const AsteriskMark({
    super.key,
    this.size = 22,
    this.color = AppTheme.ink,
  });

  final double size;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: _AsteriskPainter(color),
    );
  }
}

class _AsteriskPainter extends CustomPainter {
  _AsteriskPainter(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = size.width * 0.14
      ..strokeCap = StrokeCap.round;
    final c = Offset(size.width / 2, size.height / 2);
    final r = size.width * 0.42;
    for (var i = 0; i < 4; i++) {
      final angle = i * math.pi / 4;
      final dx = r * math.cos(angle);
      final dy = r * math.sin(angle);
      canvas.drawLine(
        Offset(c.dx - dx, c.dy - dy),
        Offset(c.dx + dx, c.dy + dy),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(covariant _AsteriskPainter oldDelegate) =>
      oldDelegate.color != color;
}

/// Small orange starburst accent used next to headlines.
class OrangeStarburst extends StatelessWidget {
  const OrangeStarburst({super.key, this.size = 28});

  final double size;

  @override
  Widget build(BuildContext context) {
    return CustomPaint(
      size: Size.square(size),
      painter: const _StarburstPainter(),
    );
  }
}

class _StarburstPainter extends CustomPainter {
  const _StarburstPainter();

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = AppTheme.primaryColor
      ..style = PaintingStyle.fill;
    final c = Offset(size.width / 2, size.height / 2);
    final outer = size.width / 2;
    final inner = outer * 0.38;
    final path = Path();
    const points = 8;
    for (var i = 0; i < points * 2; i++) {
      final radius = i.isEven ? outer : inner;
      final angle = (i * math.pi / points) - math.pi / 2;
      final x = c.dx + radius * math.cos(angle);
      final y = c.dy + radius * math.sin(angle);
      if (i == 0) {
        path.moveTo(x, y);
      } else {
        path.lineTo(x, y);
      }
    }
    path.close();
    canvas.drawPath(path, paint);
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
}

/// Brand wordmark: asterisk + ReimagineAI.
class LandingWordmark extends StatelessWidget {
  const LandingWordmark({
    super.key,
    this.color = AppTheme.ink,
    this.fontSize = 16,
  });

  final Color color;
  final double fontSize;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        AsteriskMark(size: fontSize + 4, color: color),
        const SizedBox(width: 8),
        Text(
          'ReimagineAI',
          style: GoogleFonts.interTight(
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
            letterSpacing: 0.4,
            color: color,
          ),
        ),
      ],
    );
  }
}

/// Notched image helper used across landing sections.
class NotchedImage extends StatelessWidget {
  const NotchedImage({
    super.key,
    required this.asset,
    this.corner = NotchCorner.topLeft,
    this.notchSize = 56,
    this.fit = BoxFit.cover,
    this.semanticLabel,
  });

  final String asset;
  final NotchCorner corner;
  final double notchSize;
  final BoxFit fit;
  final String? semanticLabel;

  @override
  Widget build(BuildContext context) {
    return ClipPath(
      clipper: NotchedCornerClipper(corner: corner, notchSize: notchSize),
      child: Image.asset(
        asset,
        fit: fit,
        width: double.infinity,
        height: double.infinity,
        semanticLabel: semanticLabel,
      ),
    );
  }
}
