// =========================================================================
// WhisperDnD - roster.js (Edición Laboratorio: Roster D&D Beyond & Multiclases)
// Roster oficial, 85 especies, 18 clases oficiales & homebrew, logos vectoriales
// =========================================================================

// Paleta oficial D&D Beyond (HEX exactos)
const DND_BEYOND_COLORS = {
  barbarian: '#E7623E',
  bard: '#AB6DAC',
  cleric: '#A2B5C9',
  druid: '#7A9958',
  fighter: '#7F513E',
  monk: '#51A5C5',
  paladin: '#B59E54',
  ranger: '#507F62',
  rogue: '#555752',
  sorcerer: '#CC4343',
  warlock: '#7B469B',
  wizard: '#2A52BE',
  artificer: '#E07936',
  blood_hunter: '#801C1C',
  mystic: '#4A6984',
  pugilist: '#9C4124',
  illrigger: '#5A1827',
  sidekick: '#6B7280',
  dm: '#D4AF37'
};

// Base de datos exhaustiva: 85 especies en 6 familias lógicas
const DND_DATABASE = {
  species_families: [
    {
      id: 'classic',
      name: { es: 'Especies Clásicas (PHB)', en: 'Classic Species (PHB)' },
      icon: '🛡️',
      items: [
        { id: 'human', name: { es: 'Humano', en: 'Human' } },
        { id: 'elf_high', name: { es: 'Alto Elfo', en: 'High Elf' } },
        { id: 'elf_wood', name: { es: 'Elfo de los Bosques', en: 'Wood Elf' } },
        { id: 'elf_drow', name: { es: 'Drow (Elfo Oscuro)', en: 'Dark Elf (Drow)' } },
        { id: 'elf_sea', name: { es: 'Elfo Marino', en: 'Sea Elf' } },
        { id: 'elf_shadarkai', name: { es: 'Shadar-kai (Sombrío)', en: 'Shadar-kai' } },
        { id: 'elf_eladrin', name: { es: 'Eladrin (Feérico)', en: 'Eladrin' } },
        { id: 'elf_astral', name: { es: 'Elfo Astral', en: 'Astral Elf' } },
        { id: 'elf_pallid', name: { es: 'Elfo Pálido', en: 'Pallid Elf' } },
        { id: 'dwarf_hill', name: { es: 'Enano de las Colinas', en: 'Hill Dwarf' } },
        { id: 'dwarf_mountain', name: { es: 'Enano de la Montaña', en: 'Mountain Dwarf' } },
        { id: 'dwarf_duergar', name: { es: 'Duérgar (Enano Gris)', en: 'Duergar' } },
        { id: 'halfling_lightfoot', name: { es: 'Mediano Piesligeros', en: 'Lightfoot Halfling' } },
        { id: 'halfling_stout', name: { es: 'Mediano Fornido', en: 'Stout Halfling' } },
        { id: 'halfling_ghostwise', name: { es: 'Mediano Fantasmal', en: 'Ghostwise Halfling' } },
        { id: 'halfling_lotusden', name: { es: 'Mediano Lotusden', en: 'Lotusden Halfling' } },
        { id: 'gnome_rock', name: { es: 'Gnomo de las Rocas', en: 'Rock Gnome' } },
        { id: 'gnome_forest', name: { es: 'Gnomo de los Bosques', en: 'Forest Gnome' } },
        { id: 'gnome_deep', name: { es: 'Gnomo Profundo (Svirfneblin)', en: 'Deep Gnome' } },
        { id: 'autognome', name: { es: 'Autognomo (Constructo)', en: 'Autognome' } },
        { id: 'half_elf', name: { es: 'Semielfo', en: 'Half-Elf' } },
        { id: 'half_orc', name: { es: 'Semiorco', en: 'Half-Orc' } },
        { id: 'goliath', name: { es: 'Goliat', en: 'Goliath' } },
      ]
    },
    {
      id: 'beast',
      name: { es: 'Bestiales & Antropomórficas', en: 'Beastfolk & Anthropomorphic' },
      icon: '🐾',
      items: [
        { id: 'tabaxi', name: { es: 'Tabaxi (Felino)', en: 'Tabaxi' } },
        { id: 'leonin', name: { es: 'Leonin (León de Theros)', en: 'Leonin' } },
        { id: 'aarakocra', name: { es: 'Aarakocra (Ave Rapaz)', en: 'Aarakocra' } },
        { id: 'kenku', name: { es: 'Kenku (Cuervo)', en: 'Kenku' } },
        { id: 'owlin', name: { es: 'Owlin (Hombre Búho)', en: 'Owlin' } },
        { id: 'lizardfolk', name: { es: 'Hombre Lagarto (Lizardfolk)', en: 'Lizardfolk' } },
        { id: 'tortle', name: { es: 'Tortuga (Tortle)', en: 'Tortle' } },
        { id: 'kobold', name: { es: 'Kobold', en: 'Kobold' } },
        { id: 'grung', name: { es: 'Grung (Rana Venenosa)', en: 'Grung' } },
        { id: 'harengon', name: { es: 'Harengon (Hombre Liebre)', en: 'Harengon' } },
        { id: 'loxodon', name: { es: 'Loxodon (Elefante)', en: 'Loxodon' } },
        { id: 'minotaur', name: { es: 'Minotauro', en: 'Minotaur' } },
        { id: 'centaur', name: { es: 'Centauro', en: 'Centaur' } },
        { id: 'satyr', name: { es: 'Sátiro', en: 'Satyr' } },
        { id: 'shifter_beasthide', name: { es: 'Cambiante: Piel de Bestia (Beasthide)', en: 'Beasthide Shifter' } },
        { id: 'shifter_longtooth', name: { es: 'Cambiante: Diente Largo (Longtooth)', en: 'Longtooth Shifter' } },
        { id: 'shifter_swiftstride', name: { es: 'Cambiante: Paso Rápido (Swiftstride)', en: 'Swiftstride Shifter' } },
        { id: 'shifter_wildhunt', name: { es: 'Cambiante: Caza Salvaje (Wildhunt)', en: 'Wildhunt Shifter' } },
        { id: 'locathah', name: { es: 'Locathah (Hombre Pez)', en: 'Locathah' } },
      ]
    },
    {
      id: 'planar',
      name: { es: 'Planares, Celestiales & Fiends', en: 'Planar, Celestials & Fiends' },
      icon: '🔥',
      items: [
        { id: 'tiefling_infernal', name: { es: 'Tiefling Infernal', en: 'Infernal Tiefling' } },
        { id: 'tiefling_abyssal', name: { es: 'Tiefling Abisal', en: 'Abyssal Tiefling' } },
        { id: 'tiefling_chthonic', name: { es: 'Tiefling Ctónico', en: 'Chthonic Tiefling' } },
        { id: 'tiefling_mephistopheles', name: { es: 'Tiefling de Mefistófeles', en: 'Mephistopheles Tiefling' } },
        { id: 'tiefling_zariel', name: { es: 'Tiefling de Zariel', en: 'Zariel Tiefling' } },
        { id: 'aasimar_protector', name: { es: 'Aasimar Protector', en: 'Protector Aasimar' } },
        { id: 'aasimar_scourge', name: { es: 'Aasimar Azote (Scourge)', en: 'Scourge Aasimar' } },
        { id: 'aasimar_fallen', name: { es: 'Aasimar Caído', en: 'Fallen Aasimar' } },
        { id: 'genasi_air', name: { es: 'Genasi de Aire', en: 'Air Genasi' } },
        { id: 'genasi_fire', name: { es: 'Genasi de Fuego', en: 'Fire Genasi' } },
        { id: 'genasi_earth', name: { es: 'Genasi de Tierra', en: 'Earth Genasi' } },
        { id: 'genasi_water', name: { es: 'Genasi de Agua', en: 'Water Genasi' } },
        { id: 'githyanki', name: { es: 'Githyanki (Plano Astral)', en: 'Githyanki' } },
        { id: 'githzerai', name: { es: 'Githzerai (Plano del Limbo)', en: 'Githzerai' } },
        { id: 'fairy', name: { es: 'Hada (Fairy / Pixie)', en: 'Fairy' } },
        { id: 'firbolg', name: { es: 'Firbolg', en: 'Firbolg' } },
      ]
    },
    {
      id: 'monstrous',
      name: { es: 'Monstruosas & Goblinoides', en: 'Monstrous & Goblinoids' },
      icon: '👺',
      items: [
        { id: 'goblin', name: { es: 'Goblin', en: 'Goblin' } },
        { id: 'hobgoblin', name: { es: 'Hobgoblin', en: 'Hobgoblin' } },
        { id: 'bugbear', name: { es: 'Bugbear', en: 'Bugbear' } },
        { id: 'orc', name: { es: 'Orco', en: 'Orc' } },
        { id: 'yuanti', name: { es: 'Yuan-ti (Purasangre)', en: 'Yuan-ti' } },
        { id: 'gnoll', name: { es: 'Gnoll', en: 'Gnoll' } },
      ]
    },
    {
      id: 'exotic',
      name: { es: 'Constructos & Configuraciones Espaciales', en: 'Constructs & Space Settings' },
      icon: '⚙️',
      items: [
        { id: 'warforged', name: { es: 'Forjado (Warforged de Eberron)', en: 'Warforged' } },
        { id: 'plasmoid', name: { es: 'Plasmoide (Limo Viviente)', en: 'Plasmoid' } },
        { id: 'thrikreen', name: { es: 'Thri-kreen (Insectoide Psiónico)', en: 'Thri-kreen' } },
        { id: 'giff', name: { es: 'Giff (Hipopótamo Espacial)', en: 'Giff' } },
        { id: 'hadozee', name: { es: 'Hadozee (Simio Planeador)', en: 'Hadozee' } },
        { id: 'glitchling', name: { es: 'Glitchling (Constructo de Mechanus)', en: 'Glitchling' } },
        { id: 'changeling', name: { es: 'Cambiante (Changeling de Eberron)', en: 'Changeling' } },
        { id: 'kalashtar', name: { es: 'Kalashtar', en: 'Kalashtar' } },
        { id: 'simic', name: { es: 'Híbrido Simic (Ravnica)', en: 'Simic Hybrid' } },
        { id: 'vedalken', name: { es: 'Vedalken (Ravnica)', en: 'Vedalken' } },
        { id: 'kender', name: { es: 'Kender (Dragonlance)', en: 'Kender' } },
        { id: 'verdan', name: { es: 'Verdan', en: 'Verdan' } },
      ]
    },
    {
      id: 'lineages',
      name: { es: 'Dracónidos & Linajes Sobrenaturales', en: 'Dragonborn & Supernatural Lineages' },
      icon: '🐉',
      items: [
        { id: 'dragonborn_chromatic', name: { es: 'Dracónido Cromático', en: 'Chromatic Dragonborn' } },
        { id: 'dragonborn_metallic', name: { es: 'Dracónido Metálico', en: 'Metallic Dragonborn' } },
        { id: 'dragonborn_gem', name: { es: 'Dracónido Gemario', en: 'Gem Dragonborn' } },
        { id: 'dragonborn_ravenite', name: { es: 'Dracónido Ravenite', en: 'Ravenite Dragonborn' } },
        { id: 'dhampir', name: { es: 'Dhampir (Semivampiro)', en: 'Dhampir' } },
        { id: 'hexblood', name: { es: 'Hexblood (Sangre de Bruja)', en: 'Hexblood' } },
        { id: 'reborn', name: { es: 'Reborn (Renacido)', en: 'Reborn' } },
        { id: 'hollow_one', name: { es: 'Hollow One (El Hueco)', en: 'Hollow One' } },
        { id: 'custom_lineage', name: { es: 'Linaje Personalizado (Tasha)', en: 'Custom Lineage' } },
      ]
    }
  ],

  classes: [
    {
      id: 'fighter',
      name: { es: 'Guerrero', en: 'Fighter' },
      icon: '⚔️',
      subclasses: [
        { id: 'bm', name: { es: 'Battle Master (Maestro de Batalla)', en: 'Battle Master' } },
        { id: 'champ', name: { es: 'Campeón (Champion)', en: 'Champion' } },
        { id: 'ek', name: { es: 'Caballero Sobrenatural (Eldritch Knight)', en: 'Eldritch Knight' } },
        { id: 'psi', name: { es: 'Guerrero Psiónico (Psi Warrior)', en: 'Psi Warrior' } },
        { id: 'rune', name: { es: 'Caballero Rúnico (Rune Knight)', en: 'Rune Knight' } },
        { id: 'samurai', name: { es: 'Samurái', en: 'Samurai' } },
        { id: 'echo', name: { es: 'Caballero Eco (Echo Knight)', en: 'Echo Knight' } },
        { id: 'arcane_archer', name: { es: 'Arquero Arcano (Arcane Archer)', en: 'Arcane Archer' } },
        { id: 'cavalier', name: { es: 'Caballero (Cavalier)', en: 'Cavalier' } },
        { id: 'banneret', name: { es: 'Caballero Dragón Púrpura (Banneret)', en: 'Purple Dragon Knight' } },
      ]
    },
    {
      id: 'paladin',
      name: { es: 'Paladín', en: 'Paladin' },
      icon: '🛡️',
      subclasses: [
        { id: 'devot', name: { es: 'Juramento de Devoción', en: 'Oath of Devotion' } },
        { id: 'veng', name: { es: 'Juramento de Venganza', en: 'Oath of Vengeance' } },
        { id: 'ancients', name: { es: 'Juramento de los Antiguos', en: 'Oath of the Ancients' } },
        { id: 'conquest', name: { es: 'Juramento de Conquista', en: 'Oath of Conquest' } },
        { id: 'glory', name: { es: 'Juramento de la Gloria', en: 'Oath of Glory' } },
        { id: 'redemption', name: { es: 'Juramento de Redención', en: 'Oath of Redemption' } },
        { id: 'watcher', name: { es: 'Juramento de los Vigilantes', en: 'Oath of the Watchers' } },
        { id: 'crown', name: { es: 'Juramento de la Corona (Crown)', en: 'Oath of the Crown' } },
        { id: 'oathbreaker', name: { es: 'Rompejuramentos (Oathbreaker)', en: 'Oathbreaker' } },
      ]
    },
    {
      id: 'warlock',
      name: { es: 'Brujo', en: 'Warlock' },
      icon: '👁️',
      subclasses: [
        { id: 'hexblade', name: { es: 'Filo Maldito (The Hexblade)', en: 'The Hexblade' } },
        { id: 'fiend', name: { es: 'El Infernal (The Fiend)', en: 'The Fiend' } },
        { id: 'archfey', name: { es: 'El Archihada (The Archfey)', en: 'The Archfey' } },
        { id: 'genie', name: { es: 'El Genio (The Genie)', en: 'The Genie' } },
        { id: 'celestial', name: { es: 'El Celestial', en: 'The Celestial' } },
        { id: 'great_old_one', name: { es: 'El Primigenio (Great Old One)', en: 'Great Old One' } },
        { id: 'undead', name: { es: 'El No-Muerto (The Undead)', en: 'The Undead' } },
        { id: 'fathomless', name: { es: 'Las Profundidades (The Fathomless)', en: 'The Fathomless' } },
        { id: 'undying', name: { es: 'El Inmortal (The Undying)', en: 'The Undying' } },
      ]
    },
    {
      id: 'rogue',
      name: { es: 'Pícaro', en: 'Rogue' },
      icon: '🗡️',
      subclasses: [
        { id: 'at', name: { es: 'Bribón Arcano (Arcane Trickster)', en: 'Arcane Trickster' } },
        { id: 'assassin', name: { es: 'Asesino (Assassin)', en: 'Assassin' } },
        { id: 'thief', name: { es: 'Ladrón (Thief)', en: 'Thief' } },
        { id: 'soulknife', name: { es: 'Cuchilla del Alma (Soulknife)', en: 'Soulknife' } },
        { id: 'phantom', name: { es: 'Fantasma (Phantom)', en: 'Phantom' } },
        { id: 'swashbuckler', name: { es: 'Espadachín (Swashbuckler)', en: 'Swashbuckler' } },
        { id: 'inquisitive', name: { es: 'Inquisitivo (Inquisitive)', en: 'Inquisitive' } },
        { id: 'scout', name: { es: 'Batidor (Scout)', en: 'Scout' } },
        { id: 'mastermind', name: { es: 'Mente Maestra (Mastermind)', en: 'Mastermind' } },
      ]
    },
    {
      id: 'wizard',
      name: { es: 'Mago', en: 'Wizard' },
      icon: '📜',
      subclasses: [
        { id: 'evoc', name: { es: 'Escuela de Evocación', en: 'School of Evocation' } },
        { id: 'abjur', name: { es: 'Escuela de Abjuración (Abjurer)', en: 'School of Abjuration' } },
        { id: 'necro', name: { es: 'Escuela de Nigromancia', en: 'School of Necromancy' } },
        { id: 'divin', name: { es: 'Escuela de Adivinación', en: 'School of Divination' } },
        { id: 'bladesing', name: { es: 'Canto de las Espadas (Bladesinging)', en: 'Bladesinging' } },
        { id: 'chrono', name: { es: 'Cronurgia (Chronurgy)', en: 'Chronurgy Magic' } },
        { id: 'illusion', name: { es: 'Escuela de Ilusión (Illusionist)', en: 'School of Illusion' } },
        { id: 'conjuration', name: { es: 'Escuela de Conjuración (Conjurer)', en: 'School of Conjuration' } },
        { id: 'enchantment', name: { es: 'Escuela de Encantamiento (Enchanter)', en: 'School of Enchantment' } },
        { id: 'transmutation', name: { es: 'Escuela de Transmutación (Transmuter)', en: 'School of Transmutation' } },
        { id: 'war_magic', name: { es: 'Magia de Guerra (War Magic)', en: 'War Magic' } },
        { id: 'scribes', name: { es: 'Orden de los Escribas (Order of Scribes)', en: 'Order of Scribes' } },
        { id: 'graviturgy', name: { es: 'Graviturgia (Graviturgy)', en: 'Graviturgy Magic' } },
      ]
    },
    {
      id: 'cleric',
      name: { es: 'Clérigo', en: 'Cleric' },
      icon: '✨',
      subclasses: [
        { id: 'life', name: { es: 'Dominio de la Vida', en: 'Life Domain' } },
        { id: 'light', name: { es: 'Dominio de la Luz', en: 'Light Domain' } },
        { id: 'war', name: { es: 'Dominio de la Guerra', en: 'War Domain' } },
        { id: 'tempest', name: { es: 'Dominio de la Tempestad', en: 'Tempest Domain' } },
        { id: 'twilight', name: { es: 'Dominio del Crepúsculo (Twilight)', en: 'Twilight Domain' } },
        { id: 'peace', name: { es: 'Dominio de la Paz (Peace)', en: 'Peace Domain' } },
        { id: 'forge', name: { es: 'Dominio de la Fragua (Forge)', en: 'Forge Domain' } },
        { id: 'grave', name: { es: 'Dominio de la Tumba (Grave)', en: 'Grave Domain' } },
        { id: 'death', name: { es: 'Dominio de la Muerte (Death)', en: 'Death Domain' } },
        { id: 'knowledge', name: { es: 'Dominio del Conocimiento (Knowledge)', en: 'Knowledge Domain' } },
        { id: 'nature', name: { es: 'Dominio de la Naturaleza (Nature)', en: 'Nature Domain' } },
        { id: 'order', name: { es: 'Dominio del Orden (Order)', en: 'Order Domain' } },
        { id: 'trickery', name: { es: 'Dominio del Engaño (Trickery)', en: 'Trickery Domain' } },
        { id: 'arcana', name: { es: 'Dominio Arcano (Arcana)', en: 'Arcana Domain' } },
      ]
    },
    {
      id: 'bard',
      name: { es: 'Bardo', en: 'Bard' },
      icon: '🪕',
      subclasses: [
        { id: 'lore', name: { es: 'Colegio del Saber (Lore)', en: 'College of Lore' } },
        { id: 'valor', name: { es: 'Colegio del Valor', en: 'College of Valor' } },
        { id: 'swords', name: { es: 'Colegio de las Espadas (Swords)', en: 'College of Swords' } },
        { id: 'eloquence', name: { es: 'Colegio de la Elocuencia (Eloquence)', en: 'College of Eloquence' } },
        { id: 'creation', name: { es: 'Colegio de la Creación (Creation)', en: 'College of Creation' } },
        { id: 'glamour', name: { es: 'Colegio de la Fascinación (Glamour)', en: 'College of Glamour' } },
        { id: 'whispers', name: { es: 'Colegio de los Susurros (Whispers)', en: 'College of Whispers' } },
        { id: 'dance', name: { es: 'Colegio de la Danza (Dance - 2024)', en: 'College of Dance' } },
      ]
    },
    {
      id: 'monk',
      name: { es: 'Monje', en: 'Monk' },
      icon: '👊',
      subclasses: [
        { id: 'open_hand', name: { es: 'Camino de la Mano Abierta', en: 'Way of the Open Hand' } },
        { id: 'shadow', name: { es: 'Camino de las Sombras', en: 'Way of Shadow' } },
        { id: 'mercy', name: { es: 'Camino de la Piedad (Mercy)', en: 'Way of Mercy' } },
        { id: 'kensei', name: { es: 'Camino del Kensei', en: 'Way of the Kensei' } },
        { id: 'astral_self', name: { es: 'Camino del Yo Astral (Astral Self)', en: 'Way of the Astral Self' } },
        { id: 'ascendant_dragon', name: { es: 'Camino del Dragón Ascendente', en: 'Way of the Ascendant Dragon' } },
        { id: 'drunken_master', name: { es: 'Camino del Maestro Borracho', en: 'Way of the Drunken Master' } },
        { id: 'four_elements', name: { es: 'Camino de los Cuatro Elementos', en: 'Way of the Four Elements' } },
        { id: 'long_death', name: { es: 'Camino de la Muerte Larga (Long Death)', en: 'Way of the Long Death' } },
        { id: 'sun_soul', name: { es: 'Camino del Alma Solar (Sun Soul)', en: 'Way of the Sun Soul' } },
      ]
    },
    {
      id: 'sorcerer',
      name: { es: 'Hechicero', en: 'Sorcerer' },
      icon: '🔮',
      subclasses: [
        { id: 'draconic', name: { es: 'Linaje Dracónico', en: 'Draconic Bloodline' } },
        { id: 'wild_magic', name: { es: 'Magia Salvaje', en: 'Wild Magic' } },
        { id: 'divine_soul', name: { es: 'Alma Divina (Divine Soul)', en: 'Divine Soul' } },
        { id: 'aberrant', name: { es: 'Mente Aberrante (Aberrant Mind)', en: 'Aberrant Mind' } },
        { id: 'clockwork', name: { es: 'Alma Mecánica (Clockwork Soul)', en: 'Clockwork Soul' } },
        { id: 'shadow_magic', name: { es: 'Magia Sombría (Shadow Magic)', en: 'Shadow Magic' } },
        { id: 'storm_sorcery', name: { es: 'Hechicería de Tormenta (Storm)', en: 'Storm Sorcery' } },
        { id: 'lunar_sorcery', name: { es: 'Hechicería Lunar (Lunar Sorcery)', en: 'Lunar Sorcery' } },
      ]
    },
    {
      id: 'barbarian',
      name: { es: 'Bárbaro', en: 'Barbarian' },
      icon: '🪓',
      subclasses: [
        { id: 'berserker', name: { es: 'Camino del Berserker', en: 'Path of the Berserker' } },
        { id: 'totem', name: { es: 'Camino del Guerrero Totémico', en: 'Path of the Totem Warrior' } },
        { id: 'zealot', name: { es: 'Camino del Zelote (Zealot)', en: 'Path of the Zealot' } },
        { id: 'ancestral_guardian', name: { es: 'Guardián Ancestral (Ancestral Guardian)', en: 'Path of the Ancestral Guardian' } },
        { id: 'beast', name: { es: 'Camino de la Bestia (Beast)', en: 'Path of the Beast' } },
        { id: 'storm_herald', name: { es: 'Heraldo de la Tormenta (Storm Herald)', en: 'Path of the Storm Herald' } },
        { id: 'wild_magic_barb', name: { es: 'Magia Salvaje (Wild Magic)', en: 'Path of Wild Magic' } },
        { id: 'world_tree', name: { es: 'Árbol del Mundo (World Tree - 2024)', en: 'Path of the World Tree' } },
        { id: 'battlerager', name: { es: 'Furia de Batalla (Battlerager)', en: 'Path of the Battlerager' } },
      ]
    },
    {
      id: 'druid',
      name: { es: 'Druida', en: 'Druid' },
      icon: '🌿',
      subclasses: [
        { id: 'moon', name: { es: 'Círculo de la Luna', en: 'Circle of the Moon' } },
        { id: 'stars', name: { es: 'Círculo de las Estrellas', en: 'Circle of Stars' } },
        { id: 'spores', name: { es: 'Círculo de las Esporas (Spores)', en: 'Circle of Spores' } },
        { id: 'land', name: { es: 'Círculo de la Tierra (Land)', en: 'Circle of the Land' } },
        { id: 'shepherd', name: { es: 'Círculo del Pastor (Shepherd)', en: 'Circle of the Shepherd' } },
        { id: 'wildfire', name: { es: 'Círculo del Fuego Salvaje (Wildfire)', en: 'Circle of Wildfire' } },
        { id: 'dreams', name: { es: 'Círculo de los Sueños (Dreams)', en: 'Circle of Dreams' } },
        { id: 'sea_druid', name: { es: 'Círculo del Mar (Sea - 2024)', en: 'Circle of the Sea' } },
      ]
    },
    {
      id: 'ranger',
      name: { es: 'Explorador', en: 'Ranger' },
      icon: '🏹',
      subclasses: [
        { id: 'gloom', name: { es: 'Acechador Sombrío (Gloom Stalker)', en: 'Gloom Stalker' } },
        { id: 'hunter', name: { es: 'Cazador (Hunter)', en: 'Hunter' } },
        { id: 'beast', name: { es: 'Maestro de Bestias (Beast Master)', en: 'Beast Master' } },
        { id: 'fey', name: { es: 'Caminante Feérico (Fey Wanderer)', en: 'Fey Wanderer' } },
        { id: 'drakewarden', name: { es: 'Guardián del Draco (Drakewarden)', en: 'Drakewarden' } },
        { id: 'horizon_walker', name: { es: 'Caminante del Horizonte (Horizon Walker)', en: 'Horizon Walker' } },
        { id: 'monster_slayer', name: { es: 'Cazador de Monstruos (Monster Slayer)', en: 'Monster Slayer' } },
        { id: 'swarmkeeper', name: { es: 'Guardián del Enjambre (Swarmkeeper)', en: 'Swarmkeeper' } },
      ]
    },
    {
      id: 'artificer',
      name: { es: 'Artífice', en: 'Artificer' },
      icon: '🔧',
      subclasses: [
        { id: 'armorer', name: { es: 'Armero (Armorer)', en: 'Armorer' } },
        { id: 'artillerist', name: { es: 'Artillero (Artillerist)', en: 'Artillerist' } },
        { id: 'battlesmith', name: { es: 'Herrero de Batalla (Battle Smith)', en: 'Battle Smith' } },
        { id: 'alchemist', name: { es: 'Alquimista (Alchemist)', en: 'Alchemist' } },
      ]
    },
    {
      id: 'blood_hunter',
      name: { es: 'Cazador de Sangre', en: 'Blood Hunter' },
      icon: '🩸',
      subclasses: [
        { id: 'ghostslayer', name: { es: 'Orden del Cazador Fantasma (Ghostslayer)', en: 'Order of the Ghostslayer' } },
        { id: 'profane_soul', name: { es: 'Orden del Alma Profana (Profane Soul)', en: 'Order of the Profane Soul' } },
        { id: 'mutant', name: { es: 'Orden del Mutante (Mutant)', en: 'Order of the Mutant' } },
        { id: 'lycan', name: { es: 'Orden del Licántropo (Lycanthrope)', en: 'Order of the Lycanthrope' } },
      ]
    },
    {
      id: 'mystic',
      name: { es: 'Místico (Psion)', en: 'Mystic (Psion)' },
      icon: '👁️',
      subclasses: [
        { id: 'avatar', name: { es: 'Orden del Avatar (Avatar)', en: 'Order of the Avatar' } },
        { id: 'awakened', name: { es: 'Orden del Despertado (Awakened)', en: 'Order of the Awakened' } },
        { id: 'immortal', name: { es: 'Orden del Inmortal (Immortal)', en: 'Order of the Immortal' } },
        { id: 'nomad', name: { es: 'Orden del Nómada (Nomad)', en: 'Order of the Nomad' } },
        { id: 'soulknife', name: { es: 'Orden del Alma Cuchilla (Soul Knife)', en: 'Order of the Soul Knife' } },
        { id: 'wujen', name: { es: 'Orden del Wu Jen (Wu Jen)', en: 'Order of the Wu Jen' } },
      ]
    },
    {
      id: 'pugilist',
      name: { es: 'Pugilista', en: 'Pugilist' },
      icon: '🥊',
      subclasses: [
        { id: 'boxing', name: { es: 'Rey del Cuadrilátero (Squared Circle)', en: 'Squared Circle' } },
        { id: 'street', name: { es: 'Luchador Callejero (Sweet Science)', en: 'Sweet Science' } },
        { id: 'iron_chin', name: { es: 'Mano de Hierro (Iron Chin)', en: 'Iron Chin' } },
        { id: 'prowess', name: { es: 'Peleador de Taberna (Prowess)', en: 'Prowess' } },
        { id: 'arena_royale', name: { es: 'Arena Royale (Lucha Libre)', en: 'Arena Royale' } },
        { id: 'bloodhound', name: { es: 'Sabuesos Peleadores (Bloodhound Bruisers)', en: 'Bloodhound Bruisers' } },
        { id: 'hand_of_dread', name: { es: 'Mano del Terror (Hand of Dread)', en: 'Hand of Dread' } },
        { id: 'piss_and_vinegar', name: { es: 'Vinagre y Furia (Piss & Vinegar)', en: 'Piss & Vinegar' } },
        { id: 'dog_and_bastard', name: { es: 'Perro y Bastardo (Dog & Bastard)', en: 'Dog & Bastard' } },
      ]
    },
    {
      id: 'illrigger',
      name: { es: 'Illrigger (Caballero Diabólico)', en: 'Illrigger' },
      icon: '🔱',
      subclasses: [
        { id: 'shadowmaster', name: { es: 'Sombra de Dispater (Shadowmaster)', en: 'Shadowmaster' } },
        { id: 'painkiller', name: { es: 'Caballero de Hierro (Painkiller)', en: 'Painkiller' } },
        { id: 'architect', name: { es: 'Arquitecto de Ruina (Architect of Ruin)', en: 'Architect of Ruin' } },
        { id: 'blood_knight', name: { es: 'Heraldo de Sangre (Blood Knight)', en: 'Blood Knight' } },
      ]
    },
    {
      id: 'sidekick',
      name: { es: 'Acompañante (Sidekick)', en: 'Sidekick' },
      icon: '🛡️',
      subclasses: [
        { id: 'warrior', name: { es: 'Guerrero / Protector (Warrior)', en: 'Warrior' } },
        { id: 'expert', name: { es: 'Experto / Rastreador (Expert)', en: 'Expert' } },
        { id: 'spellcaster', name: { es: 'Lanzador de Conjuros (Spellcaster)', en: 'Spellcaster' } },
      ]
    }
  ]
};

// Logos vectoriales (SVG) nativos limpios
const CLASS_VECTOR_LOGOS = {
  fighter: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="14.5 17.5 3 6 3 3 6 3 17.5 14.5"/><line x1="13" y1="19" x2="19" y2="13"/><line x1="16" y1="16" x2="20" y2="20"/><line x1="19" y1="21" x2="21" y2="19"/><polyline points="14.5 6.5 18 3 21 3 21 6 17.5 9.5"/><line x1="5" y1="14" x2="9" y2="18"/><line x1="7" y1="17" x2="4" y2="20"/><line x1="3" y1="19" x2="5" y2="21"/></svg>`,
  paladin: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><line x1="12" y1="8" x2="12" y2="16"/><line x1="8" y1="11" x2="16" y2="11"/></svg>`,
  warlock: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3-7 10-7 10 7 10 7-3 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/><path d="M12 5V2M12 22v-3M5 12H2M22 12h-3"/></svg>`,
  rogue: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 3 7 7"/><path d="m10 10 5 5 6-6-5-5-6 6Z"/><path d="m14 14 7 7"/><path d="m18 18 3 3"/></svg>`,
  wizard: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1-2.5-2.5Z"/><polyline points="10 2 10 10 13 7 16 10 16 2"/></svg>`,
  cleric: `<svg viewBox="0 0 330.7 320.04" class="w-full h-full" fill="currentColor"><g fill="currentColor"><path d="M293.5,186.58l-12.46,2.41c2.51-1.93,5.09-2.96,7.81-4.34,13.32-6.78,26.53-14.36,34.4-27.48,4.64-7.75,7.12-16.3,7.45-25.54-1.86,1.03-2.81,2.62-4.19,3.96l-11.74,11.39c-8.29,6.75-17.42,12-27.15,16.34-1.53.68-2.71,1.58-4.52,1.74l14.53-11.76c13.85-12.45,24.34-26.72,26.74-45.67.97-7.63.62-15.14-1.7-22.44-.22-.68-2.1.16-2.12.9-9.36,22.83-21.84,42.67-42.77,56.69,16.49-19.44,28.67-39.86,29.53-65.74.38-11.55-2.11-26.53-9.67-35.16-.37-.43-2.23-.89-2.27,0-.59,12.77-3.06,25.08-7.32,37.2-5.61,15.97-13.64,30.83-24.46,43.93,3.35,6.9,2.68,17.04-.11,24.02l-3.35,8.38,7.31-5.46c.93-.7,2.25-1.77,3.46-1.64,1.12.12,1.76,1.74,1.94,2.78.96,5.63-.08,11.22-2.58,16.35l-5.08,8.64c3.4-1.77,7.94-4.5,10.41-2.47.22,6.77-1.89,13.33-6.05,18.6l-6.08,5.98c3.94-1.06,9.78-2.16,9.43.31-.92,6.4-4.28,12.31-9.53,16.08l-4.69,2.73,5.95,2.23c2.03.76-3.62,8.88-11.64,11.93l-5.53,2.1,4.52,2.63c.64.37.28,1.49-.12,1.95-2.28,2.61-5.15,4.15-8.4,5.25-6.47,2.18-13.25,1.23-18.85-2.72,7.59,1.4,15.78,2.06,21.17-3.3l-4.15-2.39c-2.86-1.65-5.94-2.7-8.59-4.94,7.3.99,14.15.15,20.3-3.31,2.04-1.15,3.8-2.48,5.1-4.43l-7.41-1.52c-3.59-.73-7.16-1.06-10.46-2.49,11.25-1.54,22.44-5.3,26.17-16.49l-13.76,1.46-8.29.56,9.56-4.81c7.42-3.73,14.86-11.27,15.16-20.13l-23.76,8.42c8.3-6.32,16.76-12.24,20.4-22.07,1.29-3.48,2.11-7.01,1.62-10.79-9.03,7.07-18.21,13.07-28.45,18.37l7.93-8.47c9.41-9.66,15.69-22.27,13.36-36.22l-13.91,14.59-14.56,12.94c-11.63,10.73-16.88,26.02-14.29,41.57,2.43,14.6,0,27.41-11.61,37.06-4.46,3.71-9.09,6.37-14.23,9.44-13.93,8.34-19.77,24.86-11.63,39.84,1.4-7.53,4.57-13.94,10.63-18.2,11.66-8.19,21.9-.36,34.59,1.03l-7.51-5.74c-1.52-1.16-3.04-2.14-4.27-3.69,4.73.6,8.84,2.09,13.1,3.72,6.48,2.48,14.33,4.96,20.83,2.9.61-.19.88-.88.88-1.32,0-.68-.56-.76-1.13-1.1-4.73-2.85-9.02-6.32-12.7-10.62l11.87,3.32c7.45,2.08,15.22,1.73,22.31-1.33.52-.23.76-.86.83-1.2.05-.28-.06-.94-.57-1.05-6.37-1.41-12.42-4.48-16.99-9.23.25-.81,1.12-.87,1.83-.86l15.4.27c4.28.07,8.39-.67,12.46-1.89,2.72-.81,4.94-2.03,7.29-3.66.57-.4,1.21-2.26.16-2.38-5.68-.61-11.11-1.73-16.38-3.99-1.81-.78-3.68-1.15-5.2-2.53l10.93-1.17c11.6-1.25,23.97-6.03,29.64-17.03-5.05,1.61-9.73,2.66-14.81,2.79-5.88.14-11.5.09-17.61-1.01l15.96-4.96c14.02-5.27,27.62-14,32.57-28.65.29-.85.65-1.65-.03-2.64-9.43,6.53-19.68,11.06-30.86,13.22Z"/><path d="M112.15,228.72c-2.31-1.99-4.54-3.24-5.68-1.16l-15.37,28.09-4.32,8.74c1.47-.69,2.34-1.9,3.42-3.36l22.01-29.76c.63-.85.71-1.88-.06-2.55Z"/><path d="M84.78,201.64c-.9-.69-1.76.2-2.46.75l-25.55,19.97c-2.42,1.89-5.09,3.57-6.49,6.28l36.66-21.02c2.25-1.24.04-4.3-2.16-5.97Z"/><path d="M112.82,85.45l-21.65-28.6c-1.45-1.91-2.69-3.59-4.52-5.12.31,1.72,1.08,2.89,1.89,4.34l18.01,32.23c.47.85,1.47,1.87,2.35,1.51,2.44-.98,5.13-2.77,3.92-4.36Z"/><path d="M87.22,109l-22.99-13c-4.89-2.54-9.22-5.4-14.6-7.55,2.3,2.76,5.06,4.44,7.82,6.53l26.14,19.73c.62.47,1.53.04,1.83-.4l2.17-3.21c.39-.58.31-1.71-.38-2.1Z"/><path d="M255.33,93l-28.21,15.57c-.51.28-.85.71-.95,1.02-.14.45-.02,1,.27,1.44l2.04,3.08c.49.75,1.39,1.07,2.21.44l30.23-22.74c1.21-.91,2.24-1.65,3.04-3.05l-8.63,4.24Z"/><path d="M183.18,33.49l-2.43,7.71-8.73,33.06c-.61,2.33,3.19,3.13,6.44,2.59l4.89-39.46c.17-1.35.56-2.5-.17-3.89Z"/><path d="M220.91,59.26l-19.12,25.36c-.61.81-.76,2.06.11,2.66,1.13.78,2.43,2.02,3.98,2.21,1.03.12,1.7-1.33,2.11-2.06l16.76-30.12c.86-1.83,2.13-3.13,2.38-5.4l-6.21,7.36Z"/><path d="M139.44,64.65l-7.82-29.25c-.22-.84-.4-1.56-1.17-2.06-.1,2.84.32,5.23.66,7.98l4.24,34.15c.32,2.58,3.7,1.74,6.75,0l-2.67-10.84Z"/><path d="M73.93,174.07c-.36-.92-1.23-1.31-2.19-1.04l-24.87,7.12c-4.91,1.41-9.6,2.51-14.47,4.69,3.49.4,6.38-.44,9.66-.71l31.65-4.45c1.88-.26,1.26-2.99.23-5.62Z"/><path d="M73.7,136.77l-38.75-5.29c-.89-.12-1.62-.13-2.55.15l6.73,2.42,33.46,9.43c.74.21,1.46-.52,1.56-.99l.87-4.1c.17-.83-.53-1.51-1.33-1.62Z"/><g><path d="M202.21,132.21c-1.15.08-2.19-2.35-1.51-3.33,3.99-5.66,8.04-10.87,12.54-16.14l46.77-54.84,8.76-10.86c-2.27,1.19-3.9,2.74-5.74,4.3l-14.88,12.67-19.95,17.14-25.93,22.01c-5.1,4.33-10.02,8.4-15.75,11.85-1.1.02-2.49-.96-3.06-1.87l4.91-14.37,26.03-75.58c1.16-3.38,2.26-6.33,2.85-9.95-1.83,1.95-2.65,4.28-3.75,6.6l-5.71,12.05-25.6,54.9-5.15,11.23-4.43,8.87c-.3.6-1.34,1.85-2.06,1.17-1.4-3.7-2.08-7.5-2.82-11.49-2.78-15-4.58-29.8-5.94-45.08l-4.16-46.87c-.15-1.71-.22-3.12-.77-4.61-.63,1.02-.63,1.88-.73,2.97l-5.08,56.81c-1.28,14.29-3.34,28.16-6.13,42.16l-1.45,5.76c-.12.48-.86.55-1.18.49-.96-.18-3.17-5.28-4.43-7.99l-23.82-51.29-13.04-27.77c-1.26-2.68-2.32-5.2-4.34-7.67.43,3.7,1.87,6.88,3.03,10.32l5.41,16.04,20.24,58.61,4.81,14.04c.39,1.14-.69,1.9-1.46,2.36-.92.55-1.88.1-2.82-.57-6.12-4.3-11.81-8.86-17.55-13.77l-51.11-43.71c-4.05-3.47-7.65-6.9-12.11-9.93,1.72,3.12,3.81,5.31,6,7.88l30.23,35.37,26.04,31.06c2.35,2.8,4.33,5.49,6.2,8.64-.15,1.03-1.2,2.08-2.21,2.66l-76.22-27.05-14.04-4.76c-2.8-.95-5.28-2.34-8.55-2.52,2.36,1.67,4.63,2.99,7.27,4.24l54.47,25.7,27.45,13.05,4.88,2.68c.39.21.18,1-.1,1.2-1.84,1.4-16.42,3.6-21.6,4.19l-31.7,3.58-46.87,4.1c-2.22.19-4.17.29-6.35,1.26,6.03,1.24,11.76,1.54,17.91,2.13l45.01,4.35c8.03.78,43,4.8,44.05,7.53.14.35.18.87-.35,1.12l-54.93,25.97-31.83,15.11c-2.63,1.25-4.95,2.33-7.28,4.23l7.43-2.12,88.59-30.99c1.32-.46,2.59-.84,3.77-.78.54.32,1.35,1.74,1.08,2.41-4.15,6.37-8.71,12.03-13.62,17.78l-18.52,21.64-27.38,32.44-9.02,11.37c1.71-.76,2.84-1.78,4.2-2.97l55.13-48.16,17.08-13.91,6.08-3.98c1.24.56,2.23,1.29,3.03,2.28l-9.33,26.65-20.34,58.87c-1.59,4.61-3.4,8.88-4.05,13.83l12.55-25.71,25.27-54.27,6.72-14.11c.24-.51,1.54-.71,1.68-.11,4.6,19.15,7.43,39.03,5.41,58.61-.73,7.04-2.28,13.57-4.64,20.19l-3.53,7.22,6.88,8.94,9.42,15.39c.21.35.32.53.57.33.11-.09.26-.31.37-.5l8.68-14.43,6.14-8.15c.49-.65,1.07-1.05,1.11-1.8.04-.7-.49-1.07-.84-1.74-12.23-23.74-7.89-57.64-1.98-83.16.12-.54.38-.94.65-1.06.36-.16.94-.11,1.33.3l14.42,29.64,7-4.55-10.56-30.4c.23-1.14,2.12-2.45,3.07-2.24,3.91,2.09,7.15,4.77,10.56,7.49l12.56,10.01c1.74-6,3.68-14.95-.07-19.12l-9.18-12.69c-.2-1.02,1.54-2.66,2.58-2.36l7.11,2.07c-.04-3.93.54-7.59,1.57-11.5l-3.79-2.02c-.48-.26-.66-.68-.63-1.09.02-.28.16-.78.55-.9l6.07-1.82c1.87-4.95,4.52-9.4,8.22-13.17l6.8-6.91-20.96-4.02c-.53-.1-.76-.52-.84-.79-.11-.34-.02-.69.35-.87l12.97-6.46,30.43-14.42c2.06-.98,4.36-1.71,6.06-3.17,2.82-2.43,4.79-5.56,7.13-8.65l-39.04,13.5-22.69,7.75ZM112.99,158.39c0-24.25,19.66-43.92,43.92-43.92s43.92,19.66,43.92,43.92-19.66,43.92-43.92,43.92-43.92-19.66-43.92-43.92Z"/><circle cx="156.91" cy="158.4" r="36.23" transform="translate(-49.48 242.75) rotate(-67.5)"/></g></g></svg>`,
  bard: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>`,
  monk: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3"/><path d="M12 3a9 9 0 0 1 9 9 9 9 0 0 1-9 9 9 9 0 0 1 0-18z"/></svg>`,
  sorcerer: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>`,
  barbarian: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m14 12-8.5 8.5a2.12 2.12 0 1 1-3-3L11 9"/><path d="M15 13 9 7l4-4 6 6h3l-3 3v3l-4 4-2-2Z"/></svg>`,
  druid: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z"/><path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12"/></svg>`,
  ranger: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="m22 2-7.5 7.5"/><path d="M17 2h5v5"/><path d="m2 22 7.5-7.5"/><path d="M7 22H2v-5"/></svg>`,
  artificer: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"/></svg>`,
  blood_hunter: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v14"/><path d="M8 6h8"/><path d="M12 22s-4-3-4-6a4 4 0 0 1 8 0c0 3-4 6-4 6z" fill="currentColor"/></svg>`,
  mystic: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3" fill="currentColor" fill-opacity="0.25"/><path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41"/></svg>`,
  pugilist: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 11V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v0"/><path d="M14 10V4a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v2"/><path d="M10 10.5V6a2 2 0 0 0-2-2v0a2 2 0 0 0-2 2v8"/><path d="M18 8a2 2 0 1 1 4 0v6a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.86-5.99-2.34l-3.6-3.6a2 2 0 0 1 2.83-2.82L7 15"/></svg>`,
  illrigger: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22V2M8 5h8M7 9h10"/><path d="M5 4c0 4 2 8 7 10 5-2 7-6 7-10"/><path d="M3 2c1 5 4 9 9 11 5-2 8-6 9-11"/></svg>`,
  sidekick: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/><path d="m9 12 2 2 4-4"/></svg>`,
  dm: `<svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14v2H5v-2z"/></svg>`
};

function getClassVectorLogo(classId) {
  return CLASS_VECTOR_LOGOS[classId] || `
    <svg viewBox="0 0 24 24" class="w-full h-full" fill="none" stroke="currentColor" stroke-width="2">
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/>
    </svg>
  `;
}

// Variables de estado del Roster
let currentLang = 'es';
let cachedDiscordParticipants = [];
let _rosterDebounceTimer = null;
let activeParty = [];

let activeSpeciesRowId = null;
let activeSpeciesCatIndex = 0;

let activeClassRowId = null;
let activeClassSlot = 'primary'; // 'primary' | 'secondary'
let activeClassCatIndex = 0;

function escapeHtml(str) {
  return (str || '').replace(/[&<>'"]/g, tag => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[tag] || tag));
}

function getSelectedCampaignName() {
  const el = document.getElementById("campaignNameInput");
  return el && el.value ? el.value.trim() : "";
}

function findClassByIdOrName(val) {
  if (!val) return DND_DATABASE.classes[0];
  const clean = val.toString().trim().toLowerCase();
  const byId = DND_DATABASE.classes.find(c => c.id.toLowerCase() === clean);
  if (byId) return byId;
  const byEs = DND_DATABASE.classes.find(c => c.name.es.toLowerCase() === clean || clean.includes(c.name.es.toLowerCase()));
  if (byEs) return byEs;
  const byEn = DND_DATABASE.classes.find(c => c.name.en.toLowerCase() === clean || clean.includes(c.name.en.toLowerCase()));
  if (byEn) return byEn;
  return DND_DATABASE.classes[0];
}

// Inicializar Roster por Defecto
const DEFAULT_ROSTER = [
  {
    id: 0,
    isDM: true,
    player: "Beta",
    char: "Dungeon Master",
    discord: "",
    speciesId: "dm",
    speciesText: "(N/A - DM)",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "dm", subclassId: "dm", isCustom: false, customText: "Árbitro & Narrador" },
    secondaryClass: { active: false },
    isAbsent: false
  },
  {
    id: 1,
    isDM: false,
    player: "Roymc89",
    char: "Markus Veyl",
    discord: "",
    speciesId: "human",
    speciesText: "Humano",
    isCustomSpecies: false,
    isUserChar: true,
    primaryClass: { classId: "paladin", subclassId: "veng", isCustom: false, customText: "" },
    secondaryClass: { active: true, classId: "warlock", subclassId: "hexblade", isCustom: false, customText: "" },
    isAbsent: false
  },
  {
    id: 2,
    isDM: false,
    player: "IDarkLink",
    char: "Atou Shadowgrace",
    discord: "",
    speciesId: "elf_high",
    speciesText: "Alto Elfo",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "monk", subclassId: "shadow", isCustom: false, customText: "" },
    secondaryClass: { active: false },
    isAbsent: false
  },
  {
    id: 3,
    isDM: false,
    player: "Drowser45",
    char: "Meg'lax",
    discord: "",
    speciesId: "lizardfolk",
    speciesText: "Hombre Lagarto",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "sorcerer", subclassId: "wild_magic", isCustom: false, customText: "" },
    secondaryClass: { active: false },
    isAbsent: false
  },
  {
    id: 4,
    isDM: false,
    player: "Acher08",
    char: "Selen",
    discord: "",
    speciesId: "shifter_wildhunt",
    speciesText: "Cambiante (Shifter)",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "rogue", subclassId: "phantom", isCustom: false, customText: "" },
    secondaryClass: { active: false },
    isAbsent: false
  },
  {
    id: 5,
    isDM: false,
    player: "moonixb",
    char: "Velith",
    discord: "",
    speciesId: "tiefling_infernal",
    speciesText: "Tiefling Infernal",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "bard", subclassId: "lore", isCustom: false, customText: "" },
    secondaryClass: { active: false },
    isAbsent: false
  }
];

// Adaptar datos de la API / Base de datos a nuestro formato de Roster interactivo
function parseRawRosterToParty(rawList) {
  if (!Array.isArray(rawList) || rawList.length === 0) {
    return JSON.parse(JSON.stringify(DEFAULT_ROSTER));
  }

  const party = [];
  rawList.forEach((m, idx) => {
    const isDM = (idx === 0) || (m.character_name === "(DM)") || (m.role === "Dungeon Master (DM)");
    const rowId = idx;
    const isUserChar = Boolean(m.is_user || m.is_user_character);
    const isAbsent = Boolean(m.is_absent);
    const discordUid = (m.discord_user_id || m.discord_id || m.discord || "").toString().trim();

    if (isDM) {
      party.push({
        id: rowId,
        isDM: true,
        player: m.player_name || m.dm_name || "Beta",
        char: "Dungeon Master",
        discord: discordUid,
        speciesId: "dm",
        speciesText: "(N/A - DM)",
        isCustomSpecies: false,
        isUserChar: false,
        primaryClass: { classId: "dm", subclassId: "dm", isCustom: false, customText: "Árbitro & Narrador" },
        secondaryClass: { active: false },
        isAbsent: false
      });
      return;
    }

    // Parsing clases y multiclases
    const roleStr = (m.role || "Guerrero").trim();
    let primaryClsName = roleStr;
    let secondaryClsName = "";
    let isMulticlass = false;

    if (roleStr.includes("/") || roleStr.includes("&")) {
      const parts = roleStr.split(/[\/&]/).map(s => s.trim());
      primaryClsName = parts[0];
      secondaryClsName = parts[1] || "";
      isMulticlass = Boolean(secondaryClsName);
    } else if (m.secondary_class || m.multiclass) {
      secondaryClsName = (m.secondary_class || m.multiclass).trim();
      isMulticlass = true;
    }

    const pClsObj = findClassByIdOrName(primaryClsName);
    const sClsObj = isMulticlass ? findClassByIdOrName(secondaryClsName) : null;

    const subStr = (m.subclass || "").trim();
    let pSubId = pClsObj.subclasses[0]?.id || "";
    if (subStr) {
      const matchSub = pClsObj.subclasses.find(s => s.name.es.toLowerCase().includes(subStr.toLowerCase()) || s.name.en.toLowerCase().includes(subStr.toLowerCase()));
      if (matchSub) pSubId = matchSub.id;
    }

    party.push({
      id: rowId,
      isDM: false,
      player: m.player_name || "",
      char: m.character_name || "Aventurero",
      discord: discordUid,
      speciesId: m.species ? "custom" : "human",
      speciesText: m.species || "Humano",
      isCustomSpecies: false,
      isUserChar: isUserChar,
      primaryClass: { classId: pClsObj.id, subclassId: pSubId, isCustom: false, customText: subStr },
      secondaryClass: {
        active: isMulticlass,
        classId: sClsObj ? sClsObj.id : "warlock",
        subclassId: sClsObj ? sClsObj.subclasses[0]?.id : "hexblade",
        isCustom: false,
        customText: ""
      },
      isAbsent: isAbsent
    });
  });

  return party;
}

// Convertir de vuelta a formato de almacenamiento para el backend
function partyToStorageList(party) {
  return party.map(p => {
    if (p.isDM) {
      return {
        player_name: p.player || "Dungeon Master",
        character_name: "(DM)",
        species: "(N/A - DM)",
        role: "Dungeon Master (DM)",
        subclass: "N/A",
        discord_user_id: p.discord || "",
        discord_id: p.discord || "",
        is_user: false,
        is_user_character: false,
        is_absent: false
      };
    }

    const pCls = DND_DATABASE.classes.find(c => c.id === p.primaryClass.classId) || DND_DATABASE.classes[0];
    const pSub = pCls.subclasses.find(s => s.id === p.primaryClass.subclassId);
    const pSubLabel = p.primaryClass.isCustom ? p.primaryClass.customText : (pSub ? pSub.name.es : "");

    let roleName = pCls.name.es;
    let subName = pSubLabel;

    if (p.secondaryClass && p.secondaryClass.active) {
      const sCls = DND_DATABASE.classes.find(c => c.id === p.secondaryClass.classId) || DND_DATABASE.classes[1];
      const sSub = sCls.subclasses.find(s => s.id === p.secondaryClass.subclassId);
      const sSubLabel = p.secondaryClass.isCustom ? p.secondaryClass.customText : (sSub ? sSub.name.es : "");
      roleName = `${pCls.name.es} / ${sCls.name.es}`;
      subName = `${pSubLabel || pCls.name.es} & ${sSubLabel || sCls.name.es}`;
    }

    return {
      player_name: p.player || "",
      character_name: p.char || "Aventurero",
      species: p.isCustomSpecies ? p.customSpeciesText : (p.speciesText || "Humano"),
      role: roleName,
      subclass: subName,
      discord_user_id: p.discord || "",
      discord_id: p.discord || "",
      is_user: Boolean(p.isUserChar),
      is_user_character: Boolean(p.isUserChar),
      is_absent: Boolean(p.isAbsent)
    };
  });
}

// Render de la tabla completa de Roster
function renderRosterTable(rosterData = null) {
  if (rosterData) {
    activeParty = parseRawRosterToParty(rosterData);
  } else if (!activeParty || activeParty.length === 0) {
    activeParty = JSON.parse(JSON.stringify(DEFAULT_ROSTER));
  }

  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;

  // Pool de Discord tomada
  const takenDiscords = new Set(
    activeParty
      .filter(m => m.discord)
      .map(m => m.discord.toString().trim())
  );

  tbody.innerHTML = activeParty.map(p => {
    const availableDiscordList = (cachedDiscordParticipants || []).filter(u => {
      const uid = (u.user_id || u.id || "").toString().trim();
      return !takenDiscords.has(uid) || (p.discord && p.discord.toString().trim() === uid);
    });

    // 1. Fila del Dungeon Master
    if (p.isDM) {
      return `
        <tr class="bg-black border-b border-[#1f1f1f] hover:bg-[#0a0a0a] transition duration-150">
          <!-- Icono sutil de DM (sin recuadro cuadrado) -->
          <td class="py-3 px-2 text-center align-middle">
            <div class="flex items-center justify-center mx-auto select-none" title="Dungeon Master">
              <svg class="w-5 h-5 text-amber-500/70" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
                <path d="M2 4l3 12h14l3-12-6 7-4-7-4 7-6-7zm3 16h14v2H5v-2z"/>
              </svg>
            </div>
          </td>

          <!-- Personaje & Discord -->
          <td class="py-3 px-4 align-middle">
            <div class="space-y-1">
              <div class="text-xs font-bold text-neutral-100 font-fantasy flex items-center gap-1.5">
                <input type="text" value="${escapeHtml(p.char)}" 
                  oninput="updateCharName(${p.id}, this.value)"
                  placeholder="Dungeon Master"
                  class="bg-transparent hover:bg-[#141414] focus:bg-black border border-transparent hover:border-[#2a2a2a] focus:border-neutral-500 rounded-md px-1.5 py-0.5 text-xs font-bold text-neutral-100 outline-none w-full transition placeholder-neutral-600 truncate font-fantasy tracking-wide">
              </div>
              <div class="flex items-center gap-1.5 whitespace-nowrap min-w-0">
                <select onchange="handleDiscordSelect(${p.id}, this.value)" title="Seleccionar usuario de Discord del DM" 
                  class="discord-user-select bg-[#111111] hover:bg-[#1a1a1a] focus:bg-black border border-[#2a2a2a] hover:border-[#444] ${!p.discord ? 'text-neutral-500' : 'text-neutral-200'} font-mono text-xs rounded-lg px-2 py-0.5 outline-none cursor-pointer transition shrink-0">
                  <option value="" ${!p.discord ? 'selected' : ''}>Discord User</option>
                  ${(p.discord && !availableDiscordList.some(u => (u.user_id || u.id || '').toString().trim() === p.discord.toString().trim())) ? `<option value="${escapeHtml(p.discord)}" selected class="bg-[#121212] text-neutral-200">@${escapeHtml(p.player || p.discord)}</option>` : ''}
                  ${availableDiscordList.map(u => {
                    const uid = (u.user_id || u.id || '').toString().trim();
                    const uname = u.username || u.display_name || 'Usuario';
                    const isSel = (p.discord && p.discord.toString().trim() === uid);
                    return `<option value="${escapeHtml(uid)}" ${isSel ? 'selected' : ''} class="bg-[#121212] text-neutral-200">@${escapeHtml(uname)}</option>`;
                  }).join('')}
                </select>
                <div class="inline-flex items-center text-neutral-400 shrink-0 select-none">
                  <span class="text-neutral-500 font-mono text-[11px] leading-none">(</span>
                  <input type="text" value="${escapeHtml(p.player)}" oninput="this.style.width = (this.value ? (this.value.length + 1) : 4) + 'ch'; updatePlayerName(${p.id}, this.value)" placeholder="DM" style="width: ${p.player ? (p.player.length + 1) : 4}ch; min-width: 3ch; max-width: 18ch;" class="player-name bg-transparent hover:bg-[#1f202b] focus:bg-[#101116] border border-transparent hover:border-[#2e303e] focus:border-neutral-500 rounded px-0.5 py-0 text-xs text-neutral-300 hover:text-neutral-100 focus:text-white font-sans outline-none transition placeholder-neutral-600 text-center" title="Nombre del DM">
                  <span class="text-neutral-500 font-mono text-[11px] leading-none">)</span>
                </div>
              </div>
            </div>
          </td>

          <!-- Especie / Raza del DM (No Aplica) -->
          <td class="py-3 px-4 align-middle">
            <div class="text-xs text-neutral-500 font-mono bg-[#090909] px-3 py-2 rounded-xl border border-[#1f1f1f] text-center select-none">—</div>
          </td>

          <!-- Clase del DM: Dungeon Master -->
          <td class="py-3 px-4 align-middle">
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 flex items-center justify-center shrink-0 select-none text-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.3)]">
                ${getClassVectorLogo('dm')}
              </div>
              <div class="truncate">
                <div class="text-xs font-bold text-amber-300 font-fantasy">Dungeon Master</div>
                <div class="text-[10px] text-neutral-500 font-mono">Narrador & Árbitro</div>
              </div>
            </div>
          </td>

          <!-- Asistencia -->
          <td class="py-3 px-2 text-center align-middle">
            <div class="inline-flex items-center justify-center gap-1.5 whitespace-nowrap min-w-[88px] px-2.5 py-1 rounded-xl bg-black border border-neutral-800 select-none text-[11px] text-neutral-300">
              <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 shrink-0"></span>
              <span class="whitespace-nowrap">Presente</span>
            </div>
          </td>

          <!-- Acciones -->
          <td class="py-3 px-2 text-center align-middle">
            <span class="text-neutral-700 text-xs select-none">—</span>
          </td>
        </tr>
      `;
    }

    // 2. Fila de Jugador / Personaje Normal
    const pCls = DND_DATABASE.classes.find(c => c.id === p.primaryClass.classId) || DND_DATABASE.classes[0];
    const pSub = pCls.subclasses.find(s => s.id === p.primaryClass.subclassId);
    const pSubLabel = p.primaryClass.isCustom ? p.primaryClass.customText : (pSub ? pSub.name[currentLang] : 'Subclase');
    const pColor = DND_BEYOND_COLORS[pCls.id] || '#EDEDED';

    const sActive = p.secondaryClass && p.secondaryClass.active;
    const sCls = sActive ? (DND_DATABASE.classes.find(c => c.id === p.secondaryClass.classId) || DND_DATABASE.classes[1]) : null;
    const sSub = sCls ? sCls.subclasses.find(s => s.id === p.secondaryClass.subclassId) : null;
    const sSubLabel = sActive ? (p.secondaryClass.isCustom ? p.secondaryClass.customText : (sSub ? sSub.name[currentLang] : 'Subclase')) : '';
    const sColor = sCls ? (DND_BEYOND_COLORS[sCls.id] || '#EDEDED') : '';

    const specLabel = p.isCustomSpecies ? p.customSpeciesText : p.speciesText;
    const rowHighlight = p.isUserChar ? 'bg-[#0f0f0f] border-l-2 border-l-amber-400' : 'hover:bg-[#0a0a0a]';
    const rowDim = p.isAbsent ? 'opacity-40 grayscale-[40%]' : '';

    return `
      <tr class="${rowHighlight} ${rowDim} border-b border-[#1f1f1f] transition duration-150">
        
        <!-- Marca de Tu Personaje: Estrella Flotante Libre (sin recuadro cuadrado, un poco más grande) -->
        <td class="py-3 px-2 text-center align-middle">
          <button type="button" onclick="toggleUserChar(${p.id})"
            class="p-1 transition duration-150 flex items-center justify-center mx-auto active:scale-90 cursor-pointer ${p.isUserChar ? 'text-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.6)]' : 'text-neutral-600 hover:text-amber-400/80'}"
            title="${p.isUserChar ? 'Tu personaje en esta campaña (clic para desmarcar)' : 'Clic para marcar como tu personaje'}">
            <svg class="w-6 h-6 transition-transform" fill="${p.isUserChar ? 'currentColor' : 'none'}" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" viewBox="0 0 24 24">
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
            </svg>
          </button>
        </td>

        <!-- Personaje & Discord -->
        <td class="py-3 px-4 align-middle">
          <div class="space-y-1">
            <div class="flex items-center gap-1.5">
              <input type="text" value="${escapeHtml(p.char)}" 
                oninput="updateCharName(${p.id}, this.value)"
                placeholder="Nombre del personaje..."
                title="Clic para editar el nombre del personaje"
                class="bg-transparent hover:bg-[#141414] focus:bg-black border border-transparent hover:border-[#2a2a2a] focus:border-neutral-500 rounded-md px-1.5 py-0.5 text-xs font-bold text-neutral-100 outline-none w-full transition placeholder-neutral-600 truncate">
              ${p.isUserChar ? '<span class="text-[9px] font-mono font-bold text-amber-300 bg-amber-500/15 px-1.5 py-0.5 rounded-full border border-amber-500/30 shrink-0 select-none">Tú</span>' : ''}
            </div>

            <div class="flex items-center gap-1.5 whitespace-nowrap min-w-0">
              <select onchange="handleDiscordSelect(${p.id}, this.value)" title="Seleccionar usuario de Discord" 
                class="discord-user-select bg-[#111111] hover:bg-[#1a1a1a] focus:bg-black border border-[#2a2a2a] hover:border-[#444] ${!p.discord ? 'text-neutral-500' : 'text-neutral-200'} font-mono text-xs rounded-lg px-2 py-0.5 outline-none cursor-pointer transition shrink-0">
                <option value="" ${!p.discord ? 'selected' : ''}>Discord User</option>
                ${(p.discord && !availableDiscordList.some(u => (u.user_id || u.id || '').toString().trim() === p.discord.toString().trim())) ? `<option value="${escapeHtml(p.discord)}" selected class="bg-[#121212] text-neutral-200">@${escapeHtml(p.player || p.discord)}</option>` : ''}
                ${availableDiscordList.map(u => {
                  const uid = (u.user_id || u.id || '').toString().trim();
                  const uname = u.username || u.display_name || 'Usuario';
                  const isSel = (p.discord && p.discord.toString().trim() === uid);
                  return `<option value="${escapeHtml(uid)}" ${isSel ? 'selected' : ''} class="bg-[#121212] text-neutral-200">@${escapeHtml(uname)}</option>`;
                }).join('')}
              </select>
              <div class="inline-flex items-center text-neutral-400 shrink-0 select-none">
                <span class="text-neutral-500 font-mono text-[11px] leading-none">(</span>
                <input type="text" value="${escapeHtml(p.player)}" oninput="this.style.width = (this.value ? (this.value.length + 1) : 6) + 'ch'; updatePlayerName(${p.id}, this.value)" placeholder="Jugador" style="width: ${p.player ? (p.player.length + 1) : 6}ch; min-width: 3ch; max-width: 18ch;" class="player-name bg-transparent hover:bg-neutral-900 focus:bg-black border border-transparent hover:border-neutral-800 focus:border-neutral-700 rounded px-0.5 py-0 text-xs text-neutral-300 hover:text-neutral-100 focus:text-white font-sans outline-none transition placeholder-neutral-600 text-center" title="Nombre del jugador">
                <span class="text-neutral-500 font-mono text-[11px] leading-none">)</span>
              </div>
            </div>
          </div>
        </td>

        <!-- Especie / Raza -->
        <td class="py-3 px-4 align-middle">
          <button type="button" onclick="openSpeciesModal(${p.id})"
            class="w-full text-left px-3 py-2 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-[#444444] transition flex items-center justify-between group cursor-pointer shadow-sm">
            <span class="text-xs font-semibold text-neutral-200 group-hover:text-white truncate">${escapeHtml(specLabel)}</span>
            <span class="text-[10px] text-neutral-500 group-hover:text-neutral-300 font-mono">▼</span>
          </button>
        </td>

        <!-- Clases & Multiclases con Colores Oficiales D&D Beyond -->
        <td class="py-3 px-4 align-middle">
          ${sActive ? `
            <div class="flex items-center gap-3">
              <div class="relative shrink-0 flex items-center justify-center my-0.5 select-none" style="width: 44px; height: 44px;">
                <div class="w-10 h-10 flex items-center justify-center select-none" style="color: ${pColor};" title="Clase Principal: ${pCls.name[currentLang]}">
                  ${getClassVectorLogo(pCls.id)}
                </div>
                <div class="absolute -bottom-1 -right-1 w-5 h-5 flex items-center justify-center select-none drop-shadow-[0_2px_4px_rgba(0,0,0,0.95)]" style="color: ${sColor};" title="Multiclase: ${sCls.name[currentLang]}">
                  ${getClassVectorLogo(sCls.id)}
                </div>
              </div>

              <div class="flex-1 space-y-1 min-w-0">
                <button type="button" onclick="openClassModal(${p.id}, 'primary')"
                  class="w-full text-left px-2.5 py-1 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-[#444444] transition flex items-center justify-between group cursor-pointer shadow-sm">
                  <div class="truncate">
                    <span class="text-xs font-bold text-neutral-100 group-hover:text-white">${pCls.name[currentLang]}</span>
                    <span class="text-[10px] font-medium" style="color: ${pColor};">(${escapeHtml(pSubLabel)})</span>
                  </div>
                  <span class="text-[9px] text-neutral-500 font-mono">⚙️</span>
                </button>

                <button type="button" onclick="openClassModal(${p.id}, 'secondary')"
                  class="w-full text-left px-2.5 py-1 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-[#444444] transition flex items-center justify-between group cursor-pointer shadow-sm">
                  <div class="truncate">
                    <span class="text-xs font-bold text-neutral-100 group-hover:text-white">${sCls.name[currentLang]}</span>
                    <span class="text-[10px] font-medium" style="color: ${sColor};">(${escapeHtml(sSubLabel)})</span>
                  </div>
                  <span class="text-[9px] text-neutral-500 font-mono">⚙️</span>
                </button>
              </div>
            </div>
          ` : `
            <div class="flex items-center gap-3">
              <div class="w-10 h-10 flex items-center justify-center shrink-0 select-none my-0.5" style="color: ${pColor};" title="Clase: ${pCls.name[currentLang]}">
                ${getClassVectorLogo(pCls.id)}
              </div>
              <div class="flex-1 min-w-0">
                <button type="button" onclick="openClassModal(${p.id}, 'primary')"
                  class="w-full text-left px-3 py-1.5 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-[#444444] transition flex items-center justify-between group cursor-pointer shadow-sm">
                  <div class="truncate">
                    <span class="text-xs font-bold text-neutral-100 group-hover:text-white">${pCls.name[currentLang]}</span>
                    <span class="text-[10px] font-medium" style="color: ${pColor};">(${escapeHtml(pSubLabel)})</span>
                  </div>
                  <span class="text-[9px] text-neutral-500 font-mono">⚙️</span>
                </button>
              </div>
            </div>
          `}
        </td>

        <!-- Asistencia -->
        <td class="py-3 px-2 text-center align-middle">
          <button type="button" onclick="toggleAbsence(${p.id})"
            class="inline-flex items-center justify-center gap-1.5 whitespace-nowrap min-w-[88px] px-2.5 py-1 rounded-xl border text-[11px] font-semibold transition active:scale-95 cursor-pointer select-none ${p.isAbsent ? 'bg-[#151515] border-neutral-800 text-neutral-500 hover:text-neutral-300' : 'bg-black border-neutral-800 text-emerald-400 hover:border-emerald-500/40'}">
            <span class="w-1.5 h-1.5 rounded-full shrink-0 ${p.isAbsent ? 'bg-neutral-600' : 'bg-emerald-400'}"></span>
            <span class="whitespace-nowrap">${p.isAbsent ? 'Ausente' : 'Presente'}</span>
          </button>
        </td>

        <!-- Eliminar -->
        <td class="py-3 px-2 text-center align-middle">
          <button type="button" onclick="deletePlayer(${p.id})" title="Eliminar fila de jugador"
            class="text-neutral-500 hover:text-rose-400 p-1.5 rounded-lg hover:bg-rose-500/10 active:scale-90 transition cursor-pointer">
            ✕
          </button>
        </td>
      </tr>
    `;
  }).join("");

  renderPartyChips();
}

// Chips de Sesión Activa
function renderPartyChips() {
  const chipsList = document.getElementById("rosterChipsList");
  const countBadge = document.getElementById("rosterChipsCountBadge");
  if (!chipsList) return;

  chipsList.innerHTML = "";
  if (!activeParty || activeParty.length === 0) {
    chipsList.innerHTML = `<span class="text-xs text-neutral-500 italic py-1">Sin miembros en la mesa. Agrega jugadores usando "+ Agregar Jugador".</span>`;
    if (countBadge) countBadge.textContent = "0 participantes";
    return;
  }

  if (countBadge) {
    countBadge.textContent = `${activeParty.length} participante${activeParty.length === 1 ? '' : 's'}`;
  }

  activeParty.forEach(p => {
    const chip = document.createElement("div");
    const isUser = Boolean(p.isUserChar);
    chip.className = "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs transition duration-150 shadow-sm " +
      (p.isDM
        ? "bg-amber-500/10 border-amber-500/30 text-amber-300"
        : (isUser
          ? "bg-amber-500/20 border-amber-500/50 text-amber-200 ring-1 ring-amber-400/30"
          : "bg-[#0f0f0f] border-[#222222] text-neutral-200 hover:border-[#333333]"));

    const charName = escapeHtml(p.char || (p.isDM ? "Dungeon Master" : "Aventurero"));
    const playerName = escapeHtml(p.player || "");

    chip.innerHTML = `
      <div class="flex items-center gap-1.5">
        ${p.isDM ? '<span>👑</span>' : (isUser ? '<span class="text-amber-400">⭐</span>' : '')}
        <span class="font-semibold">${charName}</span>
        ${playerName ? `<span class="text-[10px] text-neutral-400">(${playerName})</span>` : ''}
        ${p.discord ? `<span class="text-[9px] font-mono text-sky-400 bg-sky-500/10 px-1.5 py-0.5 rounded border border-sky-500/20">@${escapeHtml(p.discord)}</span>` : ''}
      </div>
    `;
    chipsList.appendChild(chip);
  });
}

const renderRosterChips = renderPartyChips;

// Métodos de control interactivo de fila
function toggleUserChar(rowId) {
  activeParty.forEach(p => {
    if (!p.isDM) {
      p.isUserChar = (p.id === rowId) ? !p.isUserChar : false;
    }
  });
  renderRosterTable();
  saveCurrentRoster();
}

function toggleAbsence(rowId) {
  const p = activeParty.find(x => x.id === rowId);
  if (p && !p.isDM) {
    p.isAbsent = !p.isAbsent;
    renderRosterTable();
    saveCurrentRoster();
  }
}

function updateCharName(rowId, val) {
  const p = activeParty.find(x => x.id === rowId);
  if (p) {
    p.char = val;
    saveCurrentRoster();
  }
}

function updatePlayerName(rowId, val) {
  const p = activeParty.find(x => x.id === rowId);
  if (p) {
    p.player = val;
    saveCurrentRoster();
  }
}

function handleDiscordSelect(rowId, val) {
  const p = activeParty.find(x => x.id === rowId);
  if (!p) return;
  p.discord = val;
  const found = (cachedDiscordParticipants || []).find(u => (u.user_id || u.id || '').toString() === val);
  if (found && !p.player) {
    p.player = found.username || found.display_name || '';
  }
  renderRosterTable();
  saveCurrentRoster();
}

function addPlayerRow() {
  const maxId = activeParty.reduce((acc, curr) => Math.max(acc, curr.id || 0), 0);
  activeParty.push({
    id: maxId + 1,
    isDM: false,
    player: "",
    char: "Nuevo Aventurero",
    discord: "",
    speciesId: "human",
    speciesText: "Humano",
    isCustomSpecies: false,
    isUserChar: false,
    primaryClass: { classId: "fighter", subclassId: "champ", isCustom: false, customText: "" },
    secondaryClass: { active: false, classId: "", subclassId: "", isCustom: false, customText: "" },
    isAbsent: false
  });
  renderRosterTable();
  saveCurrentRoster();
}

const addRosterRow = addPlayerRow;

function deletePlayer(rowId) {
  const p = activeParty.find(x => x.id === rowId);
  if (!p || p.isDM) return;
  activeParty = activeParty.filter(x => x.id !== rowId);
  renderRosterTable();
  saveCurrentRoster();
}

// =========================================================================
// MODAL DE ESPECIES (85 ESPECIES EN 6 FAMILIAS)
// =========================================================================
function openSpeciesModal(rowId) {
  activeSpeciesRowId = rowId;
  activeSpeciesCatIndex = 0;
  const input = document.getElementById("speciesSearchInput");
  if (input) input.value = "";
  renderSpeciesCategories();
  renderSpeciesItems();
  const modal = document.getElementById("speciesModal");
  if (modal) modal.classList.remove("hidden");
}

function closeSpeciesModal() {
  const modal = document.getElementById("speciesModal");
  if (modal) modal.classList.add("hidden");
}

function renderSpeciesCategories() {
  const col = document.getElementById("speciesCategoryList");
  if (!col) return;
  col.innerHTML = DND_DATABASE.species_families.map((fam, idx) => `
    <button type="button" onclick="selectSpeciesCategory(${idx})"
      class="w-full text-left p-2.5 rounded-xl transition flex items-center justify-between cursor-pointer ${idx === activeSpeciesCatIndex ? 'bg-[#1c1c1c] text-white border border-[#333333] font-bold' : 'text-neutral-400 hover:text-white hover:bg-[#121212] border border-transparent'}">
      <div class="flex items-center gap-2 truncate">
        <span class="text-sm shrink-0">${fam.icon}</span>
        <span class="text-xs truncate">${fam.name[currentLang]}</span>
      </div>
      <span class="text-[10px] text-neutral-500 font-mono font-semibold">${fam.items.length}</span>
    </button>
  `).join("");
}

function renderSpeciesItems(filterQuery = "") {
  const col = document.getElementById("speciesItemsList");
  if (!col) return;
  const q = filterQuery.toLowerCase().trim();

  if (q) {
    let matches = [];
    DND_DATABASE.species_families.forEach(fam => {
      fam.items.forEach(it => {
        const esName = it.name.es.toLowerCase();
        const enName = it.name.en.toLowerCase();
        if (esName.includes(q) || enName.includes(q)) {
          matches.push({ item: it, familyName: fam.name[currentLang] });
        }
      });
    });

    if (matches.length === 0) {
      col.innerHTML = `
        <div class="p-6 text-center text-neutral-500 space-y-2">
          <p class="text-xs">No se encontraron especies para "<strong>${escapeHtml(q)}</strong>".</p>
          <button type="button" onclick="selectCustomSpeciesFromModal('${escapeHtml(q)}')"
            class="px-3 py-1.5 rounded-lg bg-[#181818] text-neutral-200 border border-[#333333] text-xs font-semibold hover:bg-[#222222] cursor-pointer">
            ✨ Usar "${escapeHtml(q)}" como especie Homebrew
          </button>
        </div>
      `;
      return;
    }

    col.innerHTML = `
      <div class="px-2 py-1 text-[11px] font-bold text-neutral-400 uppercase tracking-wider font-mono border-b border-[#222222] mb-2 flex items-center justify-between">
        <span>Resultados</span>
        <span class="text-neutral-200 font-bold">${matches.length} coincidencia(s)</span>
      </div>
      ${matches.map(m => `
        <button type="button" onclick="applySpeciesSelection('${m.item.id}', '${escapeHtml(m.item.name[currentLang])}')"
          class="w-full text-left p-3 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-neutral-500 transition flex items-center justify-between group cursor-pointer">
          <div>
            <div class="text-xs font-bold text-neutral-200 group-hover:text-white">${m.item.name[currentLang]}</div>
            <div class="text-[10px] text-neutral-500">${m.familyName} • ${currentLang === 'es' ? m.item.name.en : m.item.name.es}</div>
          </div>
          <span class="text-xs text-white opacity-0 group-hover:opacity-100 font-bold">Seleccionar →</span>
        </button>
      `).join("")}
    `;
    return;
  }

  const activeFam = DND_DATABASE.species_families[activeSpeciesCatIndex] || DND_DATABASE.species_families[0];
  col.innerHTML = `
    <div class="px-2 py-1 text-[11px] font-bold text-neutral-400 uppercase tracking-wider font-mono border-b border-[#222222] mb-2 flex items-center justify-between">
      <span>${activeFam.name[currentLang]}</span>
      <span class="text-neutral-400 font-mono font-bold">${activeFam.items.length} opciones</span>
    </div>
    ${activeFam.items.map(it => `
      <button type="button" onclick="applySpeciesSelection('${it.id}', '${escapeHtml(it.name[currentLang])}')"
        class="w-full text-left p-2.5 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-neutral-500 transition flex items-center justify-between group cursor-pointer">
        <div>
          <div class="text-xs font-semibold text-neutral-200 group-hover:text-white">${it.name[currentLang]}</div>
          <div class="text-[10px] text-neutral-500 font-mono">${currentLang === 'es' ? it.name.en : it.name.es}</div>
        </div>
        <span class="text-xs text-white opacity-0 group-hover:opacity-100 font-bold">✓</span>
      </button>
    `).join("")}
  `;
}

function selectSpeciesCategory(idx) {
  activeSpeciesCatIndex = idx;
  renderSpeciesCategories();
  renderSpeciesItems();
}

function onSpeciesSearch(val) {
  renderSpeciesItems(val);
}

function applySpeciesSelection(speciesId, speciesText) {
  const p = activeParty.find(x => x.id === activeSpeciesRowId);
  if (p) {
    p.speciesId = speciesId;
    p.speciesText = speciesText;
    p.isCustomSpecies = false;
    renderRosterTable();
    saveCurrentRoster();
  }
  closeSpeciesModal();
}

function selectCustomSpeciesFromModal(initialValue = '') {
  const p = activeParty.find(x => x.id === activeSpeciesRowId);
  if (!p) return;
  p.isCustomSpecies = true;
  p.customSpeciesText = initialValue || prompt('Escribe tu especie personalizada / homebrew:', 'Humano Variant') || 'Humano';
  closeSpeciesModal();
  renderRosterTable();
  saveCurrentRoster();
}

// =========================================================================
// MODAL DE CLASE & MULTICLASE
// =========================================================================
function openClassModal(rowId, initialSlot = 'primary') {
  activeClassRowId = rowId;
  activeClassSlot = initialSlot;
  activeClassCatIndex = 0;
  const input = document.getElementById("classSearchInput");
  if (input) input.value = "";

  const p = activeParty.find(x => x.id === rowId);
  if (!p) return;

  updateClassModalHeaderTabs(p);
  renderClassCategories();
  renderSubclassItems();
  const modal = document.getElementById("classModal");
  if (modal) modal.classList.remove("hidden");
}

function closeClassModal() {
  const modal = document.getElementById("classModal");
  if (modal) modal.classList.add("hidden");
}

function updateClassModalHeaderTabs(p) {
  const tabPrim = document.getElementById("modalTabPrimary");
  const tabSec = document.getElementById("modalTabSecondary");
  const primLabel = document.getElementById("modalTabPrimaryLabel");
  const secLabel = document.getElementById("modalTabSecondaryLabel");
  const primIcon = document.getElementById("modalTabPrimaryIcon");
  const secIcon = document.getElementById("modalTabSecondaryIcon");
  const toggleContainer = document.getElementById("modalMulticlassToggleContainer");

  const pCls = DND_DATABASE.classes.find(c => c.id === p.primaryClass.classId) || DND_DATABASE.classes[0];
  if (primLabel) primLabel.textContent = pCls.name[currentLang];
  if (primIcon) primIcon.innerHTML = getClassVectorLogo(pCls.id);

  const sActive = p.secondaryClass && p.secondaryClass.active;
  if (sActive && tabSec) {
    tabSec.classList.remove("hidden");
    const sCls = DND_DATABASE.classes.find(c => c.id === p.secondaryClass.classId) || DND_DATABASE.classes[1];
    if (secLabel) secLabel.textContent = sCls.name[currentLang];
    if (secIcon) secIcon.innerHTML = getClassVectorLogo(sCls.id);

    if (activeClassSlot === 'secondary') {
      tabSec.className = "px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-white text-black shadow-md cursor-pointer";
      if (tabPrim) tabPrim.className = "px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 bg-[#141414] text-neutral-400 hover:text-white border border-[#262626] cursor-pointer";
    } else {
      if (tabPrim) tabPrim.className = "px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-white text-black shadow-md cursor-pointer";
      tabSec.className = "px-3 py-1.5 rounded-xl text-xs font-semibold transition flex items-center gap-2 bg-[#141414] text-neutral-400 hover:text-white border border-[#262626] cursor-pointer";
    }

    if (toggleContainer) {
      toggleContainer.innerHTML = `
        <button type="button" onclick="disableMulticlassFromModal()"
          class="px-2.5 py-1.5 rounded-xl bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 border border-rose-500/30 text-xs font-semibold transition flex items-center gap-1.5 cursor-pointer"
          title="Quitar multiclase y regresar a clase única">
          <span>✕</span>
          <span>Quitar Multiclase</span>
        </button>
      `;
    }
  } else {
    if (tabSec) tabSec.classList.add("hidden");
    activeClassSlot = 'primary';
    if (tabPrim) tabPrim.className = "px-3 py-1.5 rounded-xl text-xs font-bold transition flex items-center gap-2 bg-white text-black shadow-md cursor-pointer";
    if (toggleContainer) {
      toggleContainer.innerHTML = `
        <button type="button" onclick="enableMulticlassFromModal()"
          class="px-3 py-1.5 rounded-xl bg-[#1c1c1c] hover:bg-[#252525] text-white border border-[#333333] text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-sm">
          <span>⚡ + Habilitar Multiclase</span>
        </button>
      `;
    }
  }
}

function switchClassModalTab(slot) {
  activeClassSlot = slot;
  const p = activeParty.find(x => x.id === activeClassRowId);
  if (!p) return;
  const targetData = slot === 'secondary' ? p.secondaryClass : p.primaryClass;
  const foundIdx = DND_DATABASE.classes.findIndex(c => c.id === targetData.classId);
  activeClassCatIndex = foundIdx >= 0 ? foundIdx : 0;
  updateClassModalHeaderTabs(p);
  renderClassCategories();
  renderSubclassItems();
}

function enableMulticlassFromModal() {
  const p = activeParty.find(x => x.id === activeClassRowId);
  if (!p) return;
  p.secondaryClass = {
    active: true,
    classId: p.primaryClass.classId === 'warlock' ? 'paladin' : 'warlock',
    subclassId: 'hexblade',
    isCustom: false,
    customText: ''
  };
  activeClassSlot = 'secondary';
  const foundIdx = DND_DATABASE.classes.findIndex(c => c.id === p.secondaryClass.classId);
  activeClassCatIndex = foundIdx >= 0 ? foundIdx : 0;
  updateClassModalHeaderTabs(p);
  renderClassCategories();
  renderSubclassItems();
  renderRosterTable();
  saveCurrentRoster();
}

function disableMulticlassFromModal() {
  const p = activeParty.find(x => x.id === activeClassRowId);
  if (!p) return;
  if (p.secondaryClass) p.secondaryClass.active = false;
  activeClassSlot = 'primary';
  const foundIdx = DND_DATABASE.classes.findIndex(c => c.id === p.primaryClass.classId);
  activeClassCatIndex = foundIdx >= 0 ? foundIdx : 0;
  updateClassModalHeaderTabs(p);
  renderClassCategories();
  renderSubclassItems();
  renderRosterTable();
  saveCurrentRoster();
}

function renderClassCategories() {
  const col = document.getElementById("classCategoryList");
  if (!col) return;
  col.innerHTML = DND_DATABASE.classes.map((cls, idx) => `
    <button type="button" onclick="selectClassCategory(${idx})"
      class="w-full text-left p-2.5 rounded-xl transition flex items-center justify-between cursor-pointer ${idx === activeClassCatIndex ? 'bg-[#1c1c1c] text-white border border-[#333333] font-bold' : 'text-neutral-400 hover:text-white hover:bg-[#121212] border border-transparent'}">
      <div class="flex items-center gap-2.5 truncate">
        <span class="w-4 h-4 shrink-0 flex items-center justify-center" style="color: ${DND_BEYOND_COLORS[cls.id] || '#ffffff'};">
          ${getClassVectorLogo(cls.id)}
        </span>
        <span class="text-xs truncate">${cls.name[currentLang]}</span>
      </div>
      <span class="text-[10px] text-neutral-500 font-mono font-semibold">${cls.subclasses.length}</span>
    </button>
  `).join("");
}

function renderSubclassItems(filterQuery = "") {
  const col = document.getElementById("classItemsList");
  if (!col) return;
  const q = filterQuery.toLowerCase().trim();

  if (q) {
    let matches = [];
    DND_DATABASE.classes.forEach(cls => {
      cls.subclasses.forEach(sub => {
        const esName = sub.name.es.toLowerCase();
        const enName = sub.name.en.toLowerCase();
        if (esName.includes(q) || enName.includes(q)) {
          matches.push({ sub, classId: cls.id, className: cls.name[currentLang] });
        }
      });
    });

    if (matches.length === 0) {
      col.innerHTML = `
        <div class="p-6 text-center text-neutral-500 space-y-2">
          <p class="text-xs">No se encontraron subclases para "<strong>${escapeHtml(q)}</strong>".</p>
          <button type="button" onclick="selectCustomClassFromModal('${escapeHtml(q)}')"
            class="px-3 py-1.5 rounded-lg bg-[#181818] text-neutral-200 border border-[#333333] text-xs font-semibold hover:bg-[#222222] cursor-pointer">
            ✨ Usar "${escapeHtml(q)}" como subclase Homebrew
          </button>
        </div>
      `;
      return;
    }

    col.innerHTML = `
      <div class="px-2 py-1 text-[11px] font-bold text-neutral-400 uppercase tracking-wider font-mono border-b border-[#222222] mb-2 flex items-center justify-between">
        <span>Resultados</span>
        <span class="text-neutral-200 font-bold">${matches.length} coincidencia(s)</span>
      </div>
      ${matches.map(m => `
        <button type="button" onclick="applySubclassSelection('${m.classId}', '${m.sub.id}')"
          class="w-full text-left p-3 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-neutral-500 transition flex items-center justify-between group cursor-pointer">
          <div>
            <div class="text-xs font-bold text-neutral-200 flex items-center gap-2 group-hover:text-white">
              <span class="w-3.5 h-3.5 shrink-0 flex items-center justify-center" style="color: ${DND_BEYOND_COLORS[m.classId] || '#ffffff'};">${getClassVectorLogo(m.classId)}</span>
              <span>${m.sub.name[currentLang]}</span>
            </div>
            <div class="text-[10px] text-neutral-500">${m.className} • ${currentLang === 'es' ? m.sub.name.en : m.sub.name.es}</div>
          </div>
          <span class="text-xs text-white opacity-0 group-hover:opacity-100 font-bold">Seleccionar →</span>
        </button>
      `).join("")}
    `;
    return;
  }

  const activeCls = DND_DATABASE.classes[activeClassCatIndex] || DND_DATABASE.classes[0];
  col.innerHTML = `
    <div class="px-2 py-1 text-[11px] font-bold text-neutral-400 uppercase tracking-wider font-mono border-b border-[#222222] mb-2 flex items-center justify-between">
      <div class="flex items-center gap-2">
        <span class="w-4 h-4 shrink-0 flex items-center justify-center" style="color: ${DND_BEYOND_COLORS[activeCls.id] || '#ffffff'};">${getClassVectorLogo(activeCls.id)}</span>
        <span>Subclases de ${activeCls.name[currentLang]}</span>
      </div>
      <span class="text-neutral-400 font-mono font-bold">${activeCls.subclasses.length} mostradas</span>
    </div>
    ${activeCls.subclasses.map(sub => `
      <button type="button" onclick="applySubclassSelection('${activeCls.id}', '${sub.id}')"
        class="w-full text-left p-2.5 rounded-xl bg-black hover:bg-[#141414] border border-[#262626] hover:border-neutral-500 transition flex items-center justify-between group cursor-pointer">
        <div>
          <div class="text-xs font-semibold text-neutral-200 group-hover:text-white">${sub.name[currentLang]}</div>
          <div class="text-[10px] text-neutral-500 font-mono">${currentLang === 'es' ? sub.name.en : sub.name.es}</div>
        </div>
        <span class="text-xs text-white opacity-0 group-hover:opacity-100 font-bold">✓</span>
      </button>
    `).join("")}
  `;
}

function selectClassCategory(idx) {
  activeClassCatIndex = idx;
  renderClassCategories();
  renderSubclassItems();
}

function onClassSearch(val) {
  renderSubclassItems(val);
}

function applySubclassSelection(classId, subclassId) {
  const p = activeParty.find(x => x.id === activeClassRowId);
  if (p) {
    const slotKey = activeClassSlot === 'secondary' ? 'secondaryClass' : 'primaryClass';
    p[slotKey].classId = classId;
    p[slotKey].subclassId = subclassId;
    p[slotKey].isCustom = false;
    updateClassModalHeaderTabs(p);
    renderRosterTable();
    saveCurrentRoster();
  }
  closeClassModal();
}

function selectCustomClassFromModal(initialValue = '') {
  const p = activeParty.find(x => x.id === activeClassRowId);
  if (!p) return;
  const slotKey = activeClassSlot === 'secondary' ? 'secondaryClass' : 'primaryClass';
  p[slotKey].isCustom = true;
  p[slotKey].customText = initialValue || prompt('Escribe tu subclase personalizada / homebrew:', 'Iniciador del Éter') || '';
  closeClassModal();
  renderRosterTable();
  saveCurrentRoster();
}

// =========================================================================
// PERSISTENCIA & COMUNICACIÓN CON EL SERVIDOR
// =========================================================================
function gatherRosterData() {
  return partyToStorageList(activeParty);
}

function getRosterFromTable(includeDM = true) {
  const list = partyToStorageList(activeParty);
  return includeDM ? list : list.slice(1);
}

async function saveRoster() {
  const campName = getSelectedCampaignName();
  if (!campName) return;
  const storageData = gatherRosterData();
  const dm = storageData[0] || {};
  const players = storageData.slice(1);

  const payload = {
    campaign_name: campName,
    dm_name: dm.player_name || "Dungeon Master",
    dm_discord_user_id: dm.discord_user_id || "",
    players: players
  };

  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}/roster`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const badge = document.getElementById("saveStatusBadge");
    if (badge) {
      badge.classList.remove("hidden");
      setTimeout(() => badge.classList.add("hidden"), 2500);
    }
  } catch (err) {
    console.warn("Error saving roster to backend:", err);
  }
}

function saveCurrentRoster() {
  clearTimeout(_rosterDebounceTimer);
  _rosterDebounceTimer = setTimeout(() => {
    saveRoster();
  }, 400);
}

function manualSaveRoster() {
  saveRoster();
  if (typeof showAlert === "function") {
    showAlert("✓ Roster oficial de campaña guardado con éxito.", "success");
  }
}

async function loadCampaignRoster(campName) {
  if (!campName) return;
  try {
    const res = await fetch(`/api/campaigns/${encodeURIComponent(campName)}`);
    if (res.ok) {
      const respData = await res.json();
      const state = respData.campaign_state || respData;
      let rawList = Array.isArray(state.roster) ? state.roster : (Array.isArray(state.players) ? state.players : []);

      const dmName = state.dm_name || state.dm || state.dungeon_master || "";
      const dmDiscord = state.dm_discord_id || state.dm_discord_user_id || state.dm_discord || "";

      if (rawList.length === 0) {
        renderRosterTable();
        return;
      }

      const hasDM = rawList.some((m, idx) => (idx === 0 && (m.character_name === "(DM)" || m.role === "Dungeon Master (DM)")) || m.character_name === "(DM)" || m.role === "Dungeon Master (DM)");
      if (!hasDM) {
        const dmItem = {
          player_name: dmName || "Dungeon Master",
          character_name: "(DM)",
          species: "(N/A - DM)",
          role: "Dungeon Master (DM)",
          subclass: "N/A",
          discord_user_id: dmDiscord,
          is_user_character: false
        };
        rawList = [dmItem, ...rawList];
      } else {
        const dmIdx = rawList.findIndex((m, idx) => (idx === 0) || m.character_name === "(DM)" || m.role === "Dungeon Master (DM)");
        if (dmIdx !== -1) {
          if (dmName && !rawList[dmIdx].player_name) rawList[dmIdx].player_name = dmName;
          if (dmDiscord && !(rawList[dmIdx].discord_user_id || rawList[dmIdx].discord_id)) {
            rawList[dmIdx].discord_user_id = dmDiscord;
          }
        }
      }
      renderRosterTable(rawList);
    }
  } catch (err) {
    console.warn("Error loading campaign roster:", err);
  }
}

const loadRoster = loadCampaignRoster;

async function refreshDiscordParticipants(manual = false) {
  const refreshBtn = document.getElementById("btn-refresh-discord");
  if (refreshBtn) refreshBtn.classList.add("opacity-50", "pointer-events-none");
  try {
    const res = await fetch("/api/discord/participants");
    if (res.ok) {
      const data = await res.json();
      cachedDiscordParticipants = Array.isArray(data.participants) ? data.participants : [];
      renderRosterTable();
      if (manual && typeof showAlert === "function") {
        showAlert(`🎧 Discord actualizado (${cachedDiscordParticipants.length} participantes detectados).`, "info");
      }
    }
  } catch (err) {
    console.warn("Error refreshing Discord participants:", err);
  } finally {
    if (refreshBtn) refreshBtn.classList.remove("opacity-50", "pointer-events-none");
  }
}

async function resetDiscordAuth() {
  try {
    const res = await fetch("/api/discord/reset-auth", { method: "POST" });
    if (res.ok) {
      if (typeof showAlert === "function") {
        showAlert("🔔 Token de Discord reiniciado. Por favor abre tu aplicación de Discord para autorizar.", "info");
      }
      await refreshDiscordParticipants(true);
    }
  } catch (err) {
    console.warn("Error resetting discord auth:", err);
  }
}

function toggleFullRosterTable(forceShow = null) {
  const card = document.getElementById("rosterFullCard");
  const btnText = document.getElementById("btnToggleFullRosterText");
  if (!card) return;
  const shouldShow = forceShow !== null ? Boolean(forceShow) : card.classList.contains("hidden");
  if (shouldShow) {
    card.classList.remove("hidden");
    if (btnText) btnText.textContent = "Ocultar Roster Completo";
  } else {
    card.classList.add("hidden");
    if (btnText) btnText.textContent = "Editar Roster Completo";
  }
}

function quickAddPartyMemberPrompt() {
  toggleFullRosterTable(true);
  addPlayerRow();
}

function editMemberDiscord(index) {
  toggleFullRosterTable(true);
  const tbody = document.getElementById("rosterTableBody");
  if (!tbody) return;
  const rows = tbody.querySelectorAll("tr");
  const row = rows[index];
  if (row) {
    const discordSelect = row.querySelector(".discord-user-select");
    if (discordSelect) {
      discordSelect.focus();
      discordSelect.classList.add("ring-2", "ring-sky-400");
      setTimeout(() => discordSelect.classList.remove("ring-2", "ring-sky-400"), 2000);
      row.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }
}

// Window Global Exports
window.DND_BEYOND_COLORS = DND_BEYOND_COLORS;
window.DND_DATABASE = DND_DATABASE;
window.CLASS_VECTOR_LOGOS = CLASS_VECTOR_LOGOS;
window.DEFAULT_ROSTER = DEFAULT_ROSTER;
window.activeParty = activeParty;
window.renderRosterTable = renderRosterTable;
window.renderPartyChips = renderPartyChips;
window.renderRosterChips = renderPartyChips;
window.gatherRosterData = gatherRosterData;
window.getRosterFromTable = getRosterFromTable;
window.saveRoster = saveRoster;
window.saveCurrentRoster = saveCurrentRoster;
window.manualSaveRoster = manualSaveRoster;
window.loadCampaignRoster = loadCampaignRoster;
window.loadRoster = loadCampaignRoster;
window.toggleUserChar = toggleUserChar;
window.toggleAbsence = toggleAbsence;
window.updateCharName = updateCharName;
window.updatePlayerName = updatePlayerName;
window.handleDiscordSelect = handleDiscordSelect;
window.addPlayerRow = addPlayerRow;
window.addRosterRow = addPlayerRow;
window.deletePlayer = deletePlayer;
window.openSpeciesModal = openSpeciesModal;
window.closeSpeciesModal = closeSpeciesModal;
window.selectSpeciesCategory = selectSpeciesCategory;
window.onSpeciesSearch = onSpeciesSearch;
window.applySpeciesSelection = applySpeciesSelection;
window.selectCustomSpeciesFromModal = selectCustomSpeciesFromModal;
window.openClassModal = openClassModal;
window.closeClassModal = closeClassModal;
window.updateClassModalHeaderTabs = updateClassModalHeaderTabs;
window.switchClassModalTab = switchClassModalTab;
window.enableMulticlassFromModal = enableMulticlassFromModal;
window.disableMulticlassFromModal = disableMulticlassFromModal;
window.renderClassCategories = renderClassCategories;
window.renderSubclassItems = renderSubclassItems;
window.selectClassCategory = selectClassCategory;
window.onClassSearch = onClassSearch;
window.applySubclassSelection = applySubclassSelection;
window.selectCustomClassFromModal = selectCustomClassFromModal;
window.refreshDiscordParticipants = refreshDiscordParticipants;
window.resetDiscordAuth = resetDiscordAuth;
window.toggleFullRosterTable = toggleFullRosterTable;
window.quickAddPartyMemberPrompt = quickAddPartyMemberPrompt;
window.editMemberDiscord = editMemberDiscord;
