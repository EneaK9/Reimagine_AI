import 'package:flutter/widgets.dart';
import 'package:image_picker/image_picker.dart';

class WebCameraCaptureController {
  Widget buildPreview() => const SizedBox.shrink();

  Future<void> start() {
    throw UnsupportedError('Web camera capture is only available on web.');
  }

  Future<XFile> capture() {
    throw UnsupportedError('Web camera capture is only available on web.');
  }

  Future<void> playPreview() async {}

  void dispose() {}
}
