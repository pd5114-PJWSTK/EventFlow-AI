import { Box, Chip, Stack, Typography } from "@mui/material";
import { AnimatePresence, motion } from "framer-motion";

interface AnimatedPipelineProps {
  title: string;
  steps: string[];
  activeStep: number;
}

export function AnimatedPipeline({ title, steps, activeStep }: AnimatedPipelineProps): JSX.Element {
  return (
    <Box sx={{ p: 2, border: "1px dashed", borderColor: "divider", borderRadius: 1, backgroundColor: "#fff" }}>
      <Typography variant="subtitle1" sx={{ mb: 1, fontWeight: 700 }}>
        {title}
      </Typography>
      <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
        {steps.map((step, index) => (
          <AnimatePresence key={step}>
            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.25, delay: index * 0.08 }}
            >
              <Chip
                label={step}
                color={index <= activeStep ? "primary" : "default"}
                variant={index <= activeStep ? "filled" : "outlined"}
              />
            </motion.div>
          </AnimatePresence>
        ))}
      </Stack>
    </Box>
  );
}
