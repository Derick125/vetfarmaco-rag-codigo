import 'package:app/core/theme/app_theme.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

double _raio(OutlinedBorder? forma) =>
    ((forma! as RoundedRectangleBorder).borderRadius as BorderRadius).topLeft.x;

void main() {
  for (final (nome, tema) in [('claro', appTheme), ('escuro', temaEscuro)]) {
    group('acabamento ($nome)', () {
      test('botões em raio 12 e alvo de toque de 48 dp ou mais', () {
        final preenchido = tema.filledButtonTheme.style!;
        final contornado = tema.outlinedButtonTheme.style!;
        final texto = tema.textButtonTheme.style!;
        for (final estilo in [preenchido, contornado, texto]) {
          expect(
            estilo.minimumSize!.resolve({})!.height,
            greaterThanOrEqualTo(48),
          );
          expect(
            estilo.minimumSize!.resolve({})!.width,
            greaterThanOrEqualTo(48),
          );
          expect(_raio(estilo.shape!.resolve({})), 12);
        }
      });

      test('campos em raio 8, com foco em azul de metileno', () {
        final decoracao = tema.inputDecorationTheme;
        expect(
          (decoracao.border! as OutlineInputBorder).borderRadius,
          BorderRadius.circular(8),
        );
        final foco = decoracao.focusedBorder! as OutlineInputBorder;
        expect(foco.borderSide.width, 2);
        expect(foco.borderSide.color, tema.colorScheme.primary);
      });

      test('chips em raio 10 e botão segmentado em raio 8', () {
        expect(_raio(tema.chipTheme.shape), 10);
        final segmentado = tema.segmentedButtonTheme.style!;
        expect(_raio(segmentado.shape!.resolve({})), 8);
        expect(segmentado.textStyle!.resolve({})!.fontSize, 16);
      });

      test('os textos de botão usam o rótulo semibold da escala', () {
        final rotulo = tema.textTheme.labelLarge!;
        expect(rotulo.fontSize, 16);
        expect(rotulo.fontWeight, FontWeight.w600);
        expect(rotulo.fontFamily, familiaSans);
      });
    });
  }
}
