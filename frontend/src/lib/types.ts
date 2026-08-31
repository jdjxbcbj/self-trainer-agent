import { z } from "zod";

export const audienceSchema = z.enum(["minor", "adult"]);
export type Audience = z.infer<typeof audienceSchema>;

export const moduleIdSchema = z.enum(["overseas", "domestic", "legal", "negotiation"]);
export type ModuleId = z.infer<typeof moduleIdSchema>;

export const riskLevelSchema = z.enum(["low", "medium", "high", "extreme"]);
export type RiskLevel = z.infer<typeof riskLevelSchema>;

export const roleSchema = z.enum(["opponent", "user"]);
export type Role = z.infer<typeof roleSchema>;

export const redLineCategorySchema = z.enum([
  "insult",
  "escalate",
  "violence",
  "illegal",
  "foreign",
  "privacy",
]);
export type RedLineCategory = z.infer<typeof redLineCategorySchema>;

export const redLineSchema = z.object({
  id: z.string().min(1),
  category: redLineCategorySchema,
  keywords: z.array(z.string().min(1)).min(1),
  severity: z.enum(["block", "penalty"]),
  message: z.string().min(1),
  alternative: z.string().min(1),
  lawRef: z.string().min(1),
});
export type RedLine = z.infer<typeof redLineSchema>;

export const scoreDimensionSchema = z.enum([
  "boundary",
  "calm",
  "legal",
  "deescalate",
  "evidence",
  "polite",
  "risk-avoid",
]);
export type ScoreDimension = z.infer<typeof scoreDimensionSchema>;

export const ruleTierSchema = z.enum(["boost", "neutral", "penalty"]);
export type RuleTier = z.infer<typeof ruleTierSchema>;

export const scoreRuleSchema = z.object({
  id: z.string().min(1),
  dimension: scoreDimensionSchema,
  tier: ruleTierSchema,
  keywords: z.array(z.string().min(1)).min(1),
  weight: z.number().int(),
  description: z.string().min(1),
});
export type ScoreRule = z.infer<typeof scoreRuleSchema>;

export const escalationLinesSchema = z.object({
  low: z.array(z.string().min(1)).min(1),
  mid: z.array(z.string().min(1)).min(1),
  high: z.array(z.string().min(1)).min(1),
  yield: z.array(z.string().min(1)).min(1),
});
export type EscalationLines = z.infer<typeof escalationLinesSchema>;

export const scenarioSchema = z.object({
  id: z.string().min(1),
  moduleId: moduleIdSchema,
  title: z.string().min(1),
  premise: z.string().min(1),
  persona: z.string().min(1),
  personaName: z.string().min(1),
  opening: z.string().min(1),
  escalationLines: escalationLinesSchema,
  successCriteria: z.array(z.string().min(1)).min(1),
  riskLevel: riskLevelSchema,
  minorSafe: z.boolean(),
  complianceNotes: z.string().min(1),
  laws: z.array(z.string().min(1)),
  critsToPass: z.number().int().positive(),
});
export type Scenario = z.infer<typeof scenarioSchema>;

export const judgementTierSchema = z.enum(["crit", "weak", "violation"]);
export type JudgementTier = z.infer<typeof judgementTierSchema>;

export const dimensionHitSchema = z.object({
  dimension: scoreDimensionSchema,
  ruleId: z.string().min(1),
});
export type DimensionHit = z.infer<typeof dimensionHitSchema>;

export const judgementSchema = z.object({
  tier: judgementTierSchema,
  score: z.number().int().min(0).max(100),
  delta: z.number().int(),
  dimensionHits: z.array(dimensionHitSchema),
  penaltyHits: z.array(z.string()),
  redLineId: z.string().nullable(),
  alternative: z.string().nullable(),
  lawRef: z.string().nullable(),
  reasoning: z.string().min(1),
});
export type Judgement = z.infer<typeof judgementSchema>;

export const dialogueTurnSchema = z.object({
  role: roleSchema,
  text: z.string(),
  judgement: judgementSchema.nullable(),
});
export type DialogueTurn = z.infer<typeof dialogueTurnSchema>;

export const dialogueStateSchema = z.object({
  scenarioId: z.string().min(1),
  turns: z.array(dialogueTurnSchema),
  confrontation: z.number().int().min(0).max(100),
  crits: z.number().int().min(0),
  violations: z.number().int().min(0),
  completed: z.boolean(),
});
export type DialogueState = z.infer<typeof dialogueStateSchema>;

export const levelTitleSchema = z.enum([
  "新手自保",
  "边界达人",
  "合规维权师",
  "高阶控场谈判官",
]);
export type LevelTitle = z.infer<typeof levelTitleSchema>;

export const badgeSchema = z.object({
  id: z.string().min(1),
  title: z.string().min(1),
  description: z.string().min(1),
});
export type Badge = z.infer<typeof badgeSchema>;

export const progressSchema = z.object({
  xp: z.number().int().min(0),
  level: z.number().int().min(1).max(4),
  completedScenarios: z.array(z.string().min(1)),
  badges: z.array(z.string().min(1)),
  cleanStreak: z.number().int().min(0),
});
export type Progress = z.infer<typeof progressSchema>;

export const debriefSchema = z.object({
  scenarioId: z.string().min(1),
  scenarioTitle: z.string().min(1),
  turns: z.number().int().min(0),
  crits: z.number().int().min(0),
  violations: z.number().int().min(0),
  finalTier: judgementTierSchema,
  xpEarned: z.number().int().min(0),
  passed: z.boolean(),
  errors: z.array(
    z.object({
      turn: z.number().int().min(0),
      text: z.string(),
      issue: z.string(),
      alternative: z.string().nullable(),
    }),
  ),
  bestLines: z.array(z.string()),
  lawsTouched: z.array(z.string()),
});
export type Debrief = z.infer<typeof debriefSchema>;

export const dialogueRequestSchema = z.object({
  scenarioId: z.string().min(1),
  history: z.array(dialogueTurnSchema),
  userText: z.string(),
  audience: audienceSchema,
});
export type DialogueRequest = z.infer<typeof dialogueRequestSchema>;

export const dialogueResponseSchema = z.object({
  judgement: judgementSchema,
  opponentReply: z.string(),
  confrontation: z.number().int().min(0).max(100),
  crits: z.number().int().min(0),
  violations: z.number().int().min(0),
  completed: z.boolean(),
});
export type DialogueResponse = z.infer<typeof dialogueResponseSchema>;
