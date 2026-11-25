import 'package:app/core/privacy/sanitizador_regex.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/consulta/domain/formulario_consulta.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  const s = SanitizadorRegex();

  group('SanitizadorRegex', () {
    test('mascara CPF com e sem pontuação', () {
      expect(s.sanitizar('CPF 123.456.789-09 ok'), 'CPF [CPF] ok');
      expect(s.sanitizar('12345678909'), '[CPF]');
    });

    test('mascara telefone com e sem DDD formatado', () {
      expect(s.sanitizar('ligar 85 98765-4321'), 'ligar [TELEFONE]');
      expect(s.sanitizar('(85) 3456-7890'), '[TELEFONE]');
    });

    test('mascara tutor, paciente com dois-pontos e prontuário', () {
      expect(
        s.sanitizar('Tutor: Maria Silva, cão com vômito'),
        'Tutor: [REMOVIDO], cão com vômito',
      );
      expect(
        s.sanitizar('Paciente: Rex; dose?'),
        'Paciente: [REMOVIDO]; dose?',
      );
      expect(s.sanitizar('prontuário nº 4521-A'), 'prontuário: [REMOVIDO]');
    });

    test('não destrói perguntas clínicas sem PII', () {
      for (final q in [
        'É seguro repetir meloxicam neste paciente?',
        'O animal tolera 0,1 mg/kg a cada 24 h?',
        'Dose de 5 mg para 4,2 kg em gato.',
      ]) {
        expect(s.sanitizar(q), q);
      }
    });
  });

  group('MontarCorpoConsulta', () {
    const montar = MontarCorpoConsulta(s);

    test('corpo espelha o ConsultaRequest e sanitiza a pergunta', () {
      final corpo = montar(
        const FormularioConsulta(
          especie: 'felino',
          pesoTexto: '4,2',
          farmacos: ['meloxicam', 'furosemida'],
          comorbidades: {'gestacao', 'epilepsia'},
          pergunta: '  Dose? tutor: Ana ',
        ),
      );
      expect(corpo.paraJson(), {
        'pergunta': 'Dose? tutor: [REMOVIDO]',
        'especie': 'felino',
        'peso_kg': 4.2,
        'farmacos': ['meloxicam', 'furosemida'],
        'comorbidades': ['epilepsia', 'gestacao'],
        'complexidade_dica': 'alta',
      });
    });

    test('campos vazios ou peso inválido não são enviados', () {
      final json = montar(
        const FormularioConsulta(pesoTexto: '999', pergunta: 'Pode?'),
      ).paraJson();
      expect(json, {'pergunta': 'Pode?', 'complexidade_dica': 'baixa'});
    });
  });
}
