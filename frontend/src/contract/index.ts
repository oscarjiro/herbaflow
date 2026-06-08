import { z } from "zod";
import contract from "../../../shared/contracts/analysis.json";

export const MODES = contract.$defs.mode.enum as ["auto", "guided"];
export const MAX_PLANTS = contract.$defs.limits.properties.max_plants.const as number;
export const modeSchema = z.enum(MODES);
