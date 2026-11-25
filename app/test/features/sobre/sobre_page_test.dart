import 'dart:io';

import 'package:app/features/sobre/presentation/pages/sobre_page.dart';
import 'package:app/features/sobre/presentation/versao_app.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Future<void> abrir(WidgetTester tester, {double escala = 1}) async {
    tester.platformDispatcher.textScaleFactorTestValue = escala;
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(const MaterialApp(home: SobrePage()));
  }

  testWidgets('traz as cinco seções e a origem das respostas', (tester) async {
    await abrir(tester);
    expect(find.text('Sobre o aplicativo'), findsOneWidget);
    for (final titulo in [
      'De onde vêm as respostas',
      'Ferramenta de apoio',
      'Privacidade',
      'Limites do sistema',
      'Versões',
    ]) {
      await tester.scrollUntilVisible(find.text(titulo), 200);
      expect(find.text(titulo), findsOneWidget);
    }
    await tester.scrollUntilVisible(
      find.text('De onde vêm as respostas'),
      -200,
    );
    expect(find.textContaining('Spinosa et al. (2017)'), findsWidgets);
    for (final bula in [
      'carprofeno',
      'fenobarbital',
      'insulina NPH',
      'ivermectina',
      'meloxicam',
      'tramadol',
    ]) {
      expect(find.textContaining(bula), findsOneWidget, reason: bula);
    }
  });

  testWidgets('diz que é apoio, não prescreve e remove dados no aparelho', (
    tester,
  ) async {
    await abrir(tester);
    await tester.scrollUntilVisible(find.text('Privacidade'), 200);
    expect(
      find.textContaining('não substitui o julgamento clínico'),
      findsOneWidget,
    );
    expect(find.textContaining('não emite prescrição'), findsOneWidget);
    expect(
      find.textContaining('removidas no próprio aparelho antes do envio'),
      findsOneWidget,
    );
    expect(find.textContaining('login nem cadastro'), findsOneWidget);
    expect(
      find.textContaining('não reconhece nomes próprios em texto livre'),
      findsOneWidget,
    );
  });

  testWidgets('lista os limites do sistema', (tester) async {
    await abrir(tester);
    await tester.scrollUntilVisible(find.text('Limites do sistema'), 200);
    for (final trecho in [
      'sete documentos',
      'uso humano ou de outra espécie',
      'Sem evidência suficiente no acervo.',
      'confiança baixa',
      'Cada consulta é independente',
      'precisa de conexão',
    ]) {
      await tester.scrollUntilVisible(find.textContaining(trecho), 100);
      expect(find.textContaining(trecho), findsOneWidget, reason: trecho);
    }
  });

  testWidgets('título das seções é cabeçalho para leitor de tela', (
    tester,
  ) async {
    final semantica = tester.ensureSemantics();
    await abrir(tester);
    final no = tester.getSemantics(find.text('De onde vêm as respostas'));
    expect(no.flagsCollection.isHeader, isTrue);
    semantica.dispose();
  });

  testWidgets('aguenta textScaleFactor 2.0', (tester) async {
    await abrir(tester, escala: 2);
    await tester.drag(find.byType(Scrollable), const Offset(0, -3000));
    await tester.pump();
    expect(tester.takeException(), isNull);
  });

  test('a versão exibida é a do pubspec.yaml', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    final versao = RegExp(
      r'^version:\s*([\d.]+)',
      multiLine: true,
    ).firstMatch(pubspec)!.group(1);
    expect(versaoApp, versao);
  });
}
