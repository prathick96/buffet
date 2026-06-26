"""
venture/engines/ — single-responsibility engines (the "agents").

Each engine has one job and a typed input/output (see venture/contracts.py):
  ScoutEngine     -> gather data + news, write/read the RAG store -> MarketSnapshot
  AnalystEngine   -> quant + qualitative read                    -> AnalysisReport
  DecisionEngine  -> fuse signals, apply RiskEngine gating/sizing -> TradeDecision
  ExecutionEngine -> place the (paper) order                      -> Fill
  LearningEngine  -> track metrics, feed adaptation/retraining    -> LearningUpdate

They are composed by venture/workflow.py into an autonomous loop.
"""
