import 'package:flutter/material.dart';

/// Non-web stub — camera capture is handled by [ImagePicker] on mobile.
Future<String?> capturePhotoWithWebcam(BuildContext context) async {
  return null;
}

bool get supportsWebcamCapture => false;
