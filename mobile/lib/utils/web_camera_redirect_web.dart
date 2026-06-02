import 'dart:html' as html;

bool redirectToCameraPlaybackFixUrl() {
  const redirectUrl = String.fromEnvironment('CAMERA_REDIRECT_URL');
  if (redirectUrl.isEmpty) {
    return false;
  }

  html.window.location.href = redirectUrl;
  return true;
}
