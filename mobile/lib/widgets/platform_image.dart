import 'dart:io' show File;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

/// Image widget that works on both mobile (`Image.file`) and web (`Image.network`).
/// Flutter Web does not support [Image.file] — it asserts and shows a red screen.
class PlatformImage extends StatelessWidget {
  const PlatformImage({
    super.key,
    required this.path,
    this.fit = BoxFit.cover,
    this.width,
    this.height,
    this.errorBuilder,
  });

  final String path;
  final BoxFit fit;
  final double? width;
  final double? height;
  final ImageErrorWidgetBuilder? errorBuilder;

  static bool get _isWebPath {
    return kIsWeb;
  }

  static bool isNetworkLike(String path) {
    return path.startsWith('http://') ||
        path.startsWith('https://') ||
        path.startsWith('blob:') ||
        path.startsWith('data:');
  }

  @override
  Widget build(BuildContext context) {
    if (_isWebPath || isNetworkLike(path)) {
      // data: URLs also work with Image.network on web / Image.memory preferred,
      // but Image.network handles http/https/blob. For data:, use memory via network
      // only if not data — Image.network supports data URIs in many cases.
      return Image.network(
        path,
        fit: fit,
        width: width,
        height: height,
        errorBuilder: errorBuilder,
      );
    }

    return Image.file(
      File(path),
      fit: fit,
      width: width,
      height: height,
      errorBuilder: errorBuilder,
    );
  }
}

/// Convenience when you already have a [File] (path may be a blob URL on web).
class PlatformFileImage extends StatelessWidget {
  const PlatformFileImage({
    super.key,
    required this.file,
    this.fit = BoxFit.cover,
    this.width,
    this.height,
    this.errorBuilder,
  });

  final File file;
  final BoxFit fit;
  final double? width;
  final double? height;
  final ImageErrorWidgetBuilder? errorBuilder;

  @override
  Widget build(BuildContext context) {
    return PlatformImage(
      path: file.path,
      fit: fit,
      width: width,
      height: height,
      errorBuilder: errorBuilder,
    );
  }
}
