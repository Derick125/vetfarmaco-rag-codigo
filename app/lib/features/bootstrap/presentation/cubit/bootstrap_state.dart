import 'package:equatable/equatable.dart';

/// Estados da tela de abertura (`docs/FRONTEND_SPEC.md` §7).
sealed class BootstrapState extends Equatable {
  const new();

  @override
  List<Object?> get props => [];
}

/// Inicializando DI, `hive_ce` e configuração.
class Carregando extends BootstrapState {
  /// Cria o estado de carregamento.
  const new();
}

/// Termo de uso clínico ainda não aceito — encaminhar para `/termo`.
class ParaTermo extends BootstrapState {
  /// Cria o estado de encaminhamento para o termo de uso.
  const new();
}

/// Termo já aceito e back-end configurado — encaminhar para `/consulta`.
class ParaConsulta extends BootstrapState {
  /// Cria o estado de encaminhamento para a consulta.
  const new();
}

/// Endereço do back-end ausente. Nunca uma tela branca: exibe mensagem e o
/// botão `Abrir ajustes`.
class FalhaConfig extends BootstrapState {
  /// Cria o estado de falha de configuração.
  const new();
}
