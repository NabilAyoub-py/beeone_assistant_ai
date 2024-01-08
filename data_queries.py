import pyttsx3



engine = pyttsx3.init()

voices = engine.getProperty('voices')

engine.setProperty('voice', 3)

engine.say("Bonjour, voici les éléments marquants de votre ferme pour la période sélectionnée. Vous avez un effectif de 0 au total.. Aucune opération n'a été réalisée.. Aucune donnée de production par variété.. 0 observations urgentes ont été créés dans votre ferme, dont 0 sont liées à la thématique Phytosanitaire. ")
engine.runAndWait()