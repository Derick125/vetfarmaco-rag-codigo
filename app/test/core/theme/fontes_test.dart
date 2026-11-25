import 'dart:io';

import 'package:app/core/theme/app_theme.dart';
import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// sha256 dos arquivos oficiais da IBM (`@ibm/plex-sans@1.1.0` e `@ibm/plex-serif@2.0.0`),
/// registrados em `docs/CREDITOS_ARTE.md`. Se um arquivo mudar, não é mais o original.
const _oficiais = {
  'IBMPlexSans-Regular.ttf':
      '975dcda37d80f038dcd143c22e33ca2d97a0cc5a929aace1c749153b0fe1afa5',
  'IBMPlexSans-Medium.ttf':
      '331c8639d7598b2cde62a911a71db195e30cb655cd6bdf2e324a7e984955f907',
  'IBMPlexSans-SemiBold.ttf':
      'a20caf8286023a6a7a85e40b1d2a4ae9fc3e3b1f9eda8f4c542dd4986af67bb1',
  'IBMPlexSans-Bold.ttf':
      '9e6c74a889a700d707613d24548fe4ffa6bc59559a0689d2cf9e133bdcdafb2f',
  'IBMPlexSerif-Regular.ttf':
      '6c490ccd38e856c674e0d163f3f40742a75058b7b935998dbfbc1745ba54e474',
  'IBMPlexSerif-Italic.ttf':
      'd28aa63cf618439712d6b459c5649af1d6d789cb911994f2357f1ce44128f163',
};

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test(
    'as fontes embarcadas são os arquivos oficiais, sem modificação',
    () async {
      for (final MapEntry(key: nome, value: esperado) in _oficiais.entries) {
        final dados = await rootBundle.load('assets/fonts/$nome');
        final hash = sha256.convert(dados.buffer.asUint8List()).toString();
        expect(hash, esperado, reason: nome);
      }
    },
  );

  test('a licença OFL acompanha as fontes', () {
    for (final nome in [
      'LICENSE-IBMPlexSans.txt',
      'LICENSE-IBMPlexSerif.txt',
    ]) {
      final texto = File('assets/fonts/$nome').readAsStringSync();
      expect(texto, contains('SIL Open Font License, Version 1.1'));
      expect(texto, contains('Reserved Font Name "Plex"'));
    }
  });

  test('o pubspec declara as famílias e não usa mais o google_fonts', () {
    final pubspec = File('pubspec.yaml').readAsStringSync();
    expect(pubspec, contains('family: IBMPlexSans'));
    expect(pubspec, contains('family: IBMPlexSerif'));
    expect(
      RegExp(r'^\s+google_fonts:', multiLine: true).hasMatch(pubspec),
      isFalse,
    );
    expect(
      File('pubspec.lock').readAsStringSync(),
      isNot(contains('google_fonts')),
    );
    expect(
      Directory('lib')
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))
          .any((f) => f.readAsStringSync().contains('google_fonts')),
      isFalse,
    );
  });

  test('o texto da interface é Plex Sans e o do acervo é Plex Serif', () {
    for (final tema in [appTheme, temaEscuro]) {
      expect(tema.textTheme.bodyLarge?.fontFamily, familiaSans);
      expect(tema.textTheme.titleLarge?.fontFamily, familiaSans);
    }
    expect(estiloEvidencia.fontFamily, familiaSerif);
  });

  test('escala tipográfica: corpo 16/24, metadados 12/16, título 20/28', () {
    final t = appTheme.textTheme;
    expect(t.bodyLarge?.fontSize, 16);
    expect(t.bodyLarge!.fontSize! * t.bodyLarge!.height!, closeTo(24, 0.01));
    expect(t.bodySmall?.fontSize, 12);
    expect(t.bodySmall!.fontSize! * t.bodySmall!.height!, closeTo(16, 0.01));
    expect(t.titleLarge?.fontSize, 20);
    expect(t.displaySmall?.fontSize, 31);
  });
}
