import 'dart:convert';
import 'dart:typed_data';

import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

import '../theme/app_theme.dart';

class BeforeAfterView extends StatelessWidget {
  final Uint8List beforeImageBytes;
  final String afterImageUrl;

  const BeforeAfterView({
    super.key,
    required this.beforeImageBytes,
    required this.afterImageUrl,
  });

  @override
  Widget build(BuildContext context) {
    final isWide = MediaQuery.of(context).size.width > 700;
    final before = _ImagePanel(
      label: 'Before',
      child: Image.memory(beforeImageBytes, fit: BoxFit.cover),
    );
    final after = _ImagePanel(
      label: 'After',
      badge: 'AI preview',
      child: _AfterImage(imageUrl: afterImageUrl),
    );

    if (isWide) {
      return Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Expanded(child: before),
          const SizedBox(width: 12),
          Expanded(child: after),
        ],
      );
    }

    return Column(children: [before, const SizedBox(height: 12), after]);
  }
}

class _ImagePanel extends StatelessWidget {
  final String label;
  final String? badge;
  final Widget child;

  const _ImagePanel({required this.label, required this.child, this.badge});

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: AppTheme.border),
        boxShadow: AppTheme.cardShadow,
      ),
      clipBehavior: Clip.antiAlias,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          AspectRatio(
            aspectRatio: 4 / 3,
            child: Stack(
              fit: StackFit.expand,
              children: [
                child,
                Positioned(left: 12, top: 12, child: _Label(text: label)),
                if (badge != null)
                  Positioned(
                    right: 12,
                    top: 12,
                    child: _Label(text: badge!, isSubtle: true),
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _AfterImage extends StatelessWidget {
  final String imageUrl;

  const _AfterImage({required this.imageUrl});

  @override
  Widget build(BuildContext context) {
    if (imageUrl.startsWith('data:')) {
      final bytes = base64Decode(imageUrl.split(',').last);
      return Image.memory(bytes, fit: BoxFit.cover);
    }

    return CachedNetworkImage(
      imageUrl: imageUrl,
      fit: BoxFit.cover,
      errorWidget: (_, _, _) => const Center(
        child: Icon(Icons.broken_image_outlined, color: AppTheme.textMuted),
      ),
      placeholder: (_, _) => const Center(child: CircularProgressIndicator()),
    );
  }
}

class _Label extends StatelessWidget {
  final String text;
  final bool isSubtle;

  const _Label({required this.text, this.isSubtle = false});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: isSubtle
            ? Colors.black.withValues(alpha: 0.5)
            : AppTheme.primaryColor.withValues(alpha: 0.95),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: GoogleFonts.dmSans(
          fontSize: 12,
          fontWeight: FontWeight.w700,
          color: Colors.white,
        ),
      ),
    );
  }
}
