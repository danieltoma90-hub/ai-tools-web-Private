/**
 * Citate afișate cât timp se generează un document.
 *
 * Multe citate faimoase circulă atribuite greșit („Be the change..." nu e
 * Gandhi verbatim, „the definition of insanity" nu e Einstein). Cele de mai jos
 * au sursă documentată; acolo unde atribuirea e tradițională, dar nu se poate
 * proba, `atribuit` face diferența vizibilă în loc s-o ascundă.
 */
export type Citat = { text: string; autor: string; atribuit?: boolean };

export const CITATE: Citat[] = [
  // Gândire, îndoială, cunoaștere
  { text: "The first principle is that you must not fool yourself — and you are the easiest person to fool.", autor: "Richard Feynman" },
  { text: "I would rather have questions that can't be answered than answers that can't be questioned.", autor: "Richard Feynman" },
  { text: "What I cannot create, I do not understand.", autor: "Richard Feynman" },
  { text: "Study hard what interests you the most, in the most undisciplined, irreverent and original manner possible.", autor: "Richard Feynman" },
  { text: "The greatest enemy of knowledge is not ignorance, it is the illusion of knowledge.", autor: "Daniel J. Boorstin" },
  { text: "The map is not the territory.", autor: "Alfred Korzybski" },
  { text: "All models are wrong, but some are useful.", autor: "George E. P. Box" },
  { text: "Not everything that counts can be counted, and not everything that can be counted counts.", autor: "William Bruce Cameron" },
  { text: "Data is not information, information is not knowledge, knowledge is not wisdom.", autor: "Clifford Stoll" },
  { text: "The unexamined life is not worth living.", autor: "Socrates, in Plato's Apology" },
  { text: "The only true wisdom is in knowing you know nothing.", autor: "Socrates", atribuit: true },
  { text: "If I have seen further it is by standing on the shoulders of giants.", autor: "Isaac Newton" },
  { text: "Nothing in life is to be feared, it is only to be understood.", autor: "Marie Curie" },
  { text: "The important thing is not to stop questioning.", autor: "Albert Einstein" },
  { text: "It's not that I'm so smart, it's just that I stay with problems longer.", autor: "Albert Einstein" },
  { text: "Imagination is more important than knowledge.", autor: "Albert Einstein" },
  { text: "Try not to become a person of success, but rather try to become a person of value.", autor: "Albert Einstein" },
  { text: "We cannot solve our problems with the same thinking we used when we created them.", autor: "Albert Einstein", atribuit: true },
  { text: "The mind is not a vessel to be filled, but a fire to be kindled.", autor: "Plutarch" },
  { text: "Learning never exhausts the mind.", autor: "Leonardo da Vinci" },
  { text: "Iron rusts from disuse; even so does inaction sap the vigour of the mind.", autor: "Leonardo da Vinci" },
  { text: "Judge a man by his questions rather than by his answers.", autor: "Voltaire", atribuit: true },
  { text: "Common sense is not so common.", autor: "Voltaire" },

  // Meșteșug, muncă, simplitate
  { text: "Programs must be written for people to read, and only incidentally for machines to execute.", autor: "Abelson & Sussman, SICP" },
  { text: "Premature optimization is the root of all evil.", autor: "Donald Knuth" },
  { text: "Simplicity is prerequisite for reliability.", autor: "Edsger W. Dijkstra" },
  { text: "There are two ways of constructing a software design: make it so simple there are obviously no deficiencies, or so complicated there are no obvious deficiencies.", autor: "C. A. R. Hoare" },
  { text: "Controlling complexity is the essence of computer programming.", autor: "Brian Kernighan" },
  { text: "Debugging is twice as hard as writing the code in the first place.", autor: "Brian Kernighan" },
  { text: "Any fool can write code that a computer can understand. Good programmers write code that humans can understand.", autor: "Martin Fowler" },
  { text: "Make it work, make it right, make it fast.", autor: "Kent Beck" },
  { text: "The best way to predict the future is to invent it.", autor: "Alan Kay" },
  { text: "Simple things should be simple, complex things should be possible.", autor: "Alan Kay" },
  { text: "The most damaging phrase in the language is: we've always done it this way.", autor: "Grace Hopper" },
  { text: "Talk is cheap. Show me the code.", autor: "Linus Torvalds" },
  { text: "If you think good architecture is expensive, try bad architecture.", autor: "Brian Foote & Joseph Yoder" },
  { text: "Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away.", autor: "Antoine de Saint-Exupéry" },
  { text: "A problem well stated is a problem half solved.", autor: "Charles Kettering" },
  { text: "In theory there is no difference between theory and practice. In practice there is.", autor: "Jan L. A. van de Snepscheut" },
  { text: "Perfect is the enemy of good.", autor: "Voltaire" },
  { text: "Well done is better than well said.", autor: "Benjamin Franklin" },
  { text: "An investment in knowledge pays the best interest.", autor: "Benjamin Franklin", atribuit: true },
  { text: "Genius is one percent inspiration and ninety-nine percent perspiration.", autor: "Thomas Edison" },
  { text: "I have not failed. I've just found ten thousand ways that won't work.", autor: "Thomas Edison", atribuit: true },
  { text: "We are what we repeatedly do. Excellence, then, is not an act, but a habit.", autor: "Will Durant, summarising Aristotle" },
  { text: "Give me six hours to chop down a tree and I will spend the first four sharpening the axe.", autor: "Abraham Lincoln", atribuit: true },
  { text: "Measure twice, cut once.", autor: "Proverb" },
  { text: "Weeks of coding can save you hours of planning.", autor: "Programmer's proverb" },
  { text: "Slow is smooth, and smooth is fast.", autor: "Proverb" },

  // Comunicare și oameni
  { text: "The single biggest problem in communication is the illusion that it has taken place.", autor: "William H. Whyte" },
  { text: "Tell me and I forget. Teach me and I remember. Involve me and I learn.", autor: "Chinese proverb" },
  { text: "Plans are worthless, but planning is everything.", autor: "Dwight D. Eisenhower" },
  { text: "It always seems impossible until it's done.", autor: "Nelson Mandela" },
  { text: "Education is the most powerful weapon which you can use to change the world.", autor: "Nelson Mandela" },
  { text: "The way to get started is to quit talking and begin doing.", autor: "Walt Disney" },
  { text: "Do not go where the path may lead; go instead where there is no path and leave a trail.", autor: "Ralph Waldo Emerson", atribuit: true },
  { text: "Whatever you are, be a good one.", autor: "Abraham Lincoln", atribuit: true },
  { text: "The best time to plant a tree was twenty years ago. The second best time is now.", autor: "Proverb" },
  { text: "Fall seven times, stand up eight.", autor: "Japanese proverb" },

  // Timp, răbdare, stoicism
  { text: "You have power over your mind — not outside events. Realise this, and you will find strength.", autor: "Marcus Aurelius" },
  { text: "Waste no more time arguing about what a good man should be. Be one.", autor: "Marcus Aurelius" },
  { text: "We suffer more often in imagination than in reality.", autor: "Seneca" },
  { text: "It is not that we have a short time to live, but that we waste much of it.", autor: "Seneca" },
  { text: "Luck is what happens when preparation meets opportunity.", autor: "Seneca", atribuit: true },
  { text: "No man ever steps in the same river twice, for it is not the same river and he is not the same man.", autor: "Heraclitus" },
  { text: "He who has a why to live can bear almost any how.", autor: "Friedrich Nietzsche" },
  { text: "A person who never made a mistake never tried anything new.", autor: "Albert Einstein", atribuit: true },
];

/** Un citat pe minut, în ordine amestecată, dar stabilă în cadrul unei așteptări. */
export function citatPentru(indice: number, samanta: number): Citat {
  // pas prim față de lungime => parcurge toată lista înainte să se repete
  const pas = 17;
  const start = samanta % CITATE.length;
  return CITATE[(start + indice * pas) % CITATE.length];
}
