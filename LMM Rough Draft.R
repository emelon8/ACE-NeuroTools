library(Matrix)
library(lme4)

MLM8_Sheet1$Condition2 <- scale(MLM8_Sheet1$Condition, center = TRUE, scale = TRUE) #centers the data (the column mean is subtracted from the values in the column) and then scales it (the centered column values are divided by the column’s standard deviation).

basic.lm <- lm(Phase ~ Condition, data = MLM8_Sheet1) #This is the basic Linear model and will show correlation between Dependent variable and Fixed Effect
summary(basic.lm)

mixed.lmer2 <- lmer(Phase ~ Condition + (1|RatID) + (1|(RatID:NeuronID)), data = MLM8_Sheet1)  # the syntax stays the same, but now the the random effect(RatID) and nesting(RatID:NeuronID) are taken into account
summary(mixed.lmer2)

#Plots the data
library(ggplot2)
library(ggiraph)
library(ggeffects)

pred.mm <- ggpredict(mixed.lmer2, terms = c("Condition"))  # this gives overall predictions for the model
# Plot the predictions
(ggplot(pred.mm) + geom_line(aes(x = x, y = predicted)) + geom_ribbon(aes(x = x, ymin = predicted - std.error, ymax = predicted + std.error),fill = "lightgrey", alpha = 0.5) +  # error band
geom_point(data = MLM8_Sheet1,                      # adding the raw data (scaled values)
aes(x = NeuronID, y = Phase, colour = Condition)) +labs(x = "NeuronID", y = "Phase",title = "Phase of Neurons") + theme_minimal())