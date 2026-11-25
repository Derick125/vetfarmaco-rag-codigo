import 'package:equatable/equatable.dart';

/// Estados da introdução de primeiro uso (`docs/FRONTEND_SPEC.md` §21).
sealed class IntroducaoState extends Equatable {
  const new();

  @override
  List<Object?> get props => [];
}

/// Lendo se a introdução já foi vista.
class IntroducaoCarregando extends IntroducaoState {
  /// Cria o estado.
  const new();
}

/// Primeira vez: mostrar os cartões.
class IntroducaoExibindo extends IntroducaoState {
  /// Cria o estado.
  const new();
}

/// Já vista antes: seguir direto para `/consulta`.
class IntroducaoJaVista extends IntroducaoState {
  /// Cria o estado.
  const new();
}

/// Concluída ou pulada agora: seguir para `/consulta`.
class IntroducaoConcluida extends IntroducaoState {
  /// Cria o estado.
  const new();
}
