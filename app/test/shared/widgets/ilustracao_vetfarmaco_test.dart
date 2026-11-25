import 'dart:io';

import 'package:app/shared/widgets/ilustracao_vetfarmaco.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

/// (largura, altura, tipo de cor) do cabeçalho IHDR de um PNG; tipo 6 = RGBA.
(int, int, int) _ihdr(String caminho) {
  final bytes = File(caminho).readAsBytesSync();
  final dados = ByteData.sublistView(Uint8List.fromList(bytes.sublist(0, 33)));
  return (dados.getUint32(16), dados.getUint32(20), bytes[25]);
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('PNG exportados (1x, 2x e 3x, claro e escuro)', () {
    for (final cena in Cena.values) {
      for (final tema in ['claro', 'escuro']) {
        test('${cena.arquivo}_$tema: três densidades, alfa e proporção', () {
          final base = 'assets/img/${cena.arquivo}_$tema.png';
          final (w1, h1, cor1) = _ihdr(base);
          final (w2, h2, cor2) = _ihdr(
            'assets/img/2.0x/${cena.arquivo}_$tema.png',
          );
          final (w3, h3, cor3) = _ihdr(
            'assets/img/3.0x/${cena.arquivo}_$tema.png',
          );
          expect(w1, cena.larguraPadrao.round(), reason: '1x = largura em dp');
          expect((w2, h2), (w1 * 2, h1 * 2));
          expect((w3, h3), (w1 * 3, h1 * 3));
          expect(
            [cor1, cor2, cor3],
            everyElement(6),
            reason: 'fundo transparente',
          );
        });

        test(
          '${cena.arquivo}_$tema está declarado no pubspec (carrega do bundle)',
          () async {
            final dados = await rootBundle.load(
              'assets/img/${cena.arquivo}_$tema.png',
            );
            expect(dados.lengthInBytes, greaterThan(1000));
          },
        );
      }
    }
  });

  group('IlustracaoVetFarmaco', () {
    Widget app(ThemeData tema, Widget filho) => MaterialApp(
      theme: tema,
      home: Scaffold(body: Center(child: filho)),
    );

    AssetImage provedor(WidgetTester tester) =>
        tester.widget<Image>(find.byType(Image)).image as AssetImage;

    testWidgets('escolhe o PNG do tema atual', (tester) async {
      const w = IlustracaoVetFarmaco(cena: Cena.historicoVazio);
      await tester.pumpWidget(app(ThemeData(), w));
      expect(
        provedor(tester).assetName,
        'assets/img/historico_vazio_claro.png',
      );
      await tester.pumpWidget(app(ThemeData.dark(), w));
      await tester.pumpAndSettle();
      expect(
        provedor(tester).assetName,
        'assets/img/historico_vazio_escuro.png',
      );
    });

    testWidgets('usa a largura padrão da cena ou a pedida', (tester) async {
      await tester.pumpWidget(
        app(ThemeData(), const IlustracaoVetFarmaco(cena: Cena.abertura)),
      );
      expect(tester.getSize(find.byType(Image)).width, 300);
      await tester.pumpWidget(
        app(
          ThemeData(),
          const IlustracaoVetFarmaco(cena: Cena.abertura, largura: 120),
        ),
      );
      expect(tester.getSize(find.byType(Image)).width, 120);
    });

    testWidgets('é decorativa: fora do leitor de tela', (tester) async {
      final semantica = tester.ensureSemantics();
      await tester.pumpWidget(
        app(ThemeData(), const IlustracaoVetFarmaco(cena: Cena.introCartao1)),
      );
      expect(
        tester.widget<Image>(find.byType(Image)).excludeFromSemantics,
        isTrue,
      );
      expect(find.bySemanticsLabel(RegExp('.')), findsNothing);
      semantica.dispose();
    });

    testWidgets('sem o arquivo, não quebra a tela', (tester) async {
      // O errorBuilder devolve um espaço da mesma largura.
      await tester.pumpWidget(
        app(
          ThemeData(),
          const IlustracaoVetFarmaco(cena: Cena.sobreFaixa, largura: 200),
        ),
      );
      expect(tester.takeException(), isNull);
    });
  });
}
