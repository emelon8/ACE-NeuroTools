library(Matrix)
library(lme4)

neuron_phase <- read.csv("neuron_phase.csv")

# Might not be neeed for the independent variable. https://ourcodingclub.github.io/tutorials/mixed-models/ only shows this being done on the independent variable.
#neuron_phase$Phase2 <- scale(neuron_phase$Phase, center = TRUE, scale = TRUE) #centers the data (the column mean is subtracted from the values in the column) and then scales it (the centered column values are divided by the column's standard deviation).

basic.lm <- lm(Phase ~ Condition, data = neuron_phase) #This is the basic Linear model and will show correlation between Dependent variable and Fixed Effect
summary(basic.lm)

#neuron_phase <- within(neuron_phase, neuron_no <- factor(RatID:NeuronID)) # Not sure if this is needed or not, but it may help explicitly say that there is, e.g., a neuron 0 for Rat 1 and a neuron 0 for Rat 2.

mixed.lmer2 <- lmer(Phase ~ Condition + (1|RatID) + (1|RatID:NeuronID), data = neuron_phase)  # the syntax stays the same, but now the the random effect(RatID) and nesting(RatID:NeuronID) are taken into account
summary(mixed.lmer2)

#Plots the data
library(ggplot2)
library(ggiraph)
library(ggeffects)

pred.mm <- ggpredict(mixed.lmer2, terms = c("Condition"))  # this gives overall predictions for the model
# Plot the predictions
ggplot(pred.mm) + geom_line(aes(x = x, y = predicted)) + geom_ribbon(aes(x = x, ymin = predicted - std.error, ymax = predicted + std.error),fill = "lightgrey", alpha = 0.5) +  # error band
geom_point(data = neuron_phase,                                                                                                                                                  # adding the raw data (scaled values)
aes(x = NeuronID, y = Phase, colour = Condition)) +labs(x = "NeuronID", y = "Phase",title = "Phase of Neurons") + theme_minimal()