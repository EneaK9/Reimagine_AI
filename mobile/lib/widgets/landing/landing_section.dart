import 'package:flutter/material.dart';

/// Max-width content wrapper with responsive horizontal padding.
class LandingSection extends StatelessWidget {
  const LandingSection({
    super.key,
    required this.child,
    this.maxWidth = 1200,
    this.padding,
    this.backgroundColor,
  });

  final Widget child;
  final double maxWidth;
  final EdgeInsetsGeometry? padding;
  final Color? backgroundColor;

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    final horizontal = width < 600 ? 20.0 : (width < 900 ? 32.0 : 48.0);

    return ColoredBox(
      color: backgroundColor ?? Colors.transparent,
      child: Center(
        child: ConstrainedBox(
          constraints: BoxConstraints(maxWidth: maxWidth),
          child: Padding(
            padding: padding ??
                EdgeInsets.symmetric(horizontal: horizontal, vertical: 48),
            child: child,
          ),
        ),
      ),
    );
  }
}
