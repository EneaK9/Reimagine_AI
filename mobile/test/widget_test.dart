import 'package:flutter_test/flutter_test.dart';
import 'package:reimagine_ai/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    // Build our app and trigger a frame.
    await tester.pumpWidget(const ReimagineAIApp());

    // Verify the app title is shown
    expect(find.text('ReimagineAI'), findsOneWidget);
  });
}
