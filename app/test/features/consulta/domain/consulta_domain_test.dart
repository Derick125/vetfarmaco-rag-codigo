import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:flutter_test/flutter_test.dart';

const _vocab = Vocabulario(
  versao: 'v1',
  especies: ['canino', 'felino'],
  farmacos: [
    FarmacoVocabulario(nome: 'meloxicam', sinonimos: ['Metacam']),
    FarmacoVocabulario(nome: 'furosemida'),
    FarmacoVocabulario(nome: 'carprofeno', sinonimos: ['Rimadyl']),
    FarmacoVocabulario(nome: 'fenobarbital'),
  ],
  comorbidades: [],
);

void main() {
  group('Vocabulario.sugerir', () {
    test('vazio não sugere nada', () => expect(_vocab.sugerir('  '), isEmpty));

    test('casa por prefixo, sinônimo e trecho, sem caixa nem acento', () {
      expect(_vocab.sugerir('MELOX'), ['meloxicam']);
      expect(_vocab.sugerir('metacam'), ['meloxicam']);
      expect(_vocab.sugerir('barbi'), ['fenobarbital']);
      expect(_vocab.sugerir('fúro'), ['furosemida']);
    });

    test('prefixo vem antes de trecho e exclui os já escolhidos', () {
      expect(_vocab.sugerir('ro'), ['furosemida', 'carprofeno']);
      expect(_vocab.sugerir('r', excluir: {'Carprofeno'}), [
        'furosemida',
        'fenobarbital',
      ]);
    });
  });

  group('FormularioConsulta', () {
    test('espécie e pergunta são obrigatórias', () {
      expect(const FormularioConsulta().valido, isFalse);
      expect(const FormularioConsulta(especie: 'felino').valido, isFalse);
      expect(const FormularioConsulta(pergunta: 'Pode?').valido, isFalse);
      expect(
        const FormularioConsulta(especie: 'felino', pergunta: 'Pode?').valido,
        isTrue,
      );
      expect(
        const FormularioConsulta(especie: 'felino', pergunta: ' ab ').valido,
        isFalse,
      );
    });

    test('pergunta posológica exige peso', () {
      for (final p in ['Qual a dose de meloxicam?', 'Posso dar 5 mg?']) {
        final f = FormularioConsulta(especie: 'felino', pergunta: p);
        expect(f.perguntaPosologica, isTrue, reason: p);
        expect(f.faltaPeso, isTrue, reason: p);
        expect(f.valido, isFalse, reason: p);
        expect(f.copiar(pesoTexto: '4,2').valido, isTrue, reason: p);
      }
      const f = FormularioConsulta(
        especie: 'felino',
        pergunta: 'É seguro repetir meloxicam neste paciente?',
      );
      expect(f.perguntaPosologica, isFalse);
      expect(f.valido, isTrue);
    });

    test('interpreta peso com vírgula ou ponto', () {
      expect(interpretarPeso('4,2'), 4.2);
      expect(interpretarPeso(' 4.2 '), 4.2);
      expect(interpretarPeso('abc'), isNull);
    });

    test('peso vazio é aceito; fora de (0, 200] é erro', () {
      expect(const FormularioConsulta().erroPeso, isNull);
      for (final t in ['0', '-1', '200,1', '1,2,3']) {
        final f = FormularioConsulta(especie: 'canino', pesoTexto: t);
        expect(f.erroPeso, isNotNull, reason: t);
        expect(f.valido, isFalse, reason: t);
      }
      expect(const FormularioConsulta(pesoTexto: '200').erroPeso, isNull);
    });

    test('sem fármacos é aviso, não bloqueio', () {
      const f = FormularioConsulta(especie: 'canino', pergunta: 'Pode?');
      expect(f.semFarmacos, isTrue);
      expect(f.valido, isTrue);
    });

    test('complexidade alta com 2+ fármacos ou uma comorbidade', () {
      expect(const FormularioConsulta().complexidade, 'baixa');
      expect(const FormularioConsulta(farmacos: ['a']).complexidade, 'baixa');
      expect(
        const FormularioConsulta(farmacos: ['a', 'b']).complexidade,
        'alta',
      );
      expect(
        const FormularioConsulta(comorbidades: {'epilepsia'}).complexidade,
        'alta',
      );
    });
  });
}
