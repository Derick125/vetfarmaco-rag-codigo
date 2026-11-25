import 'package:app/shared/widgets/icone_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

PintorIconeVetFarmaco _pintor(WidgetTester tester) {
  final pintura = tester.widget<CustomPaint>(
    find.descendant(
      of: find.byType(IconeVetFarmaco),
      matching: find.byType(CustomPaint),
    ),
  );
  return pintura.painter! as PintorIconeVetFarmaco;
}

void main() {
  Future<void> montar(WidgetTester tester, Widget filho) =>
      tester.pumpWidget(MaterialApp(home: Center(child: filho)));

  testWidgets('32 dp ou menos usa só a cápsula, sem a pata', (tester) async {
    await montar(tester, const IconeVetFarmaco(tamanho: 32));
    expect(_pintor(tester).compacto, isTrue);
    await montar(tester, const IconeVetFarmaco(tamanho: 20));
    expect(_pintor(tester).compacto, isTrue);
  });

  testWidgets('mais de 32 dp mantém a pata', (tester) async {
    await montar(tester, const IconeVetFarmaco(tamanho: 33));
    expect(_pintor(tester).compacto, isFalse);
    await montar(tester, const IconeVetFarmaco(tamanho: 72));
    expect(_pintor(tester).compacto, isFalse);
  });

  testWidgets('avatar é circular e tem o tamanho pedido', (tester) async {
    await montar(tester, const AvatarVetFarmaco());
    expect(find.byType(ClipOval), findsOneWidget);
    expect(tester.getSize(find.byType(IconeVetFarmaco)), const Size(32, 32));
  });

  testWidgets('a marca tem o nome falado e o ícone decorativo', (tester) async {
    final semantica = tester.ensureSemantics();
    await montar(tester, const MarcaVetFarmaco());
    expect(find.bySemanticsLabel('VetFarmaco'), findsOneWidget);
    expect(find.byType(IconeVetFarmaco), findsOneWidget);
    semantica.dispose();
  });

  testWidgets('a marca aguenta fonte 2.0 em 380 px sem estourar', (
    tester,
  ) async {
    tester.view
      ..physicalSize = const Size(380, 800)
      ..devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await montar(tester, const MarcaVetFarmaco());
    expect(tester.takeException(), isNull);
    expect(
      tester.getSize(find.byType(MarcaVetFarmaco)).width,
      lessThanOrEqualTo(380),
    );
  });
}
