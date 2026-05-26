import { Router, type IRouter } from "express";
import healthRouter from "./health";
import transactionsRouter from "./transactions";
import telegramRouter from "./telegram";

const router: IRouter = Router();

router.use(healthRouter);
router.use(transactionsRouter);
router.use(telegramRouter);

export default router;
