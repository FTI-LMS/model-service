import re
from typing import Dict, List, Set, Optional


class ContentAnalyzer:
    """Enhanced content analysis for video transcripts"""

    def __init__(self):
        self.topic_patterns = {
            'Technology': [
                r'\b(?:python|javascript|java|c\+\+|programming|code|coding|software|development|api|database|algorithm)\b',
                r'\b(?:machine learning|artificial intelligence|data science|web development|mobile app|cloud computing)\b',
                r'\b(?:cybersecurity|network|server|framework|library|git|docker|kubernetes)\b'
            ],
            'Business': [
                r'\b(?:management|leadership|strategy|marketing|sales|finance|accounting|budget)\b',
                r'\b(?:project management|team building|communication|negotiation|customer service)\b',
                r'\b(?:entrepreneurship|startup|business plan|roi|revenue|profit|analytics)\b'
            ],
            'Health': [
                r'\b(?:medical|healthcare|patient|clinical|diagnosis|treatment|therapy)\b',
                r'\b(?:wellness|nutrition|fitness|mental health|safety|first aid)\b',
                r'\b(?:pharmaceutical|nursing|surgery|anatomy|physiology)\b'
            ],
            'Education': [
                r'\b(?:teaching|learning|curriculum|pedagogy|assessment|classroom)\b',
                r'\b(?:student|education|academic|research|university|college)\b',
                r'\b(?:lesson plan|instructional design|e-learning|training)\b'
            ]
        }

        self.instructor_patterns = [
            r"(?:I'm|I am|My name is|This is|Hello,?\s*I'm|Hi,?\s*I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"Welcome.*?(?:I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            r"(?:taught by|instructor|teacher|presenter|facilitator|trainer)(?:\s+is)?\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"([A-Z][a-z]+\s+[A-Z][a-z]+).*?(?:will be|am|is)\s+(?:teaching|presenting|leading|training|instructing)",
            r"(?:Your instructor|Your teacher|Your trainer)(?:\s+is)?\s+([A-Z][a-z]+\s+[A-Z][a-z]+)"
        ]

    def extract_comprehensive_topics(self, transcript: str) -> str:
        """Extract specific training topics and concepts from transcript"""
        if not transcript:
            return "No content available for analysis"

        # Convert to lowercase for analysis
        text_lower = transcript.lower()
        training_topics = set()

        # Enhanced pattern matching for specific training concepts
        training_concept_patterns = [
            # Technical concepts
            r'\b(?:java|python|javascript|c\+\+|sql|html|css|react|angular|spring|hibernate)\s+(?:programming|development|framework|concepts?|basics?|advanced?|fundamentals?)\b',
            r'\b(?:multithreading|collections?|exception handling|object.oriented|database design|api development|microservices|design patterns?)\b',
            r'\b(?:agile|scrum|kanban|devops|ci/cd|testing|debugging|version control|git)\b',

            # Business and soft skills
            r'\b(?:client|customer|stakeholder)\s+(?:engagement|communication|relationship|management|service)\b',
            r'\b(?:project|team|time|resource|risk|change)\s+(?:management|leadership|planning|coordination)\b',
            r'\b(?:presentation|communication|negotiation|problem.solving|critical thinking|decision making)\s+(?:skills?|techniques?|methods?)\b',
            r'\b(?:sales|marketing|finance|accounting|business)\s+(?:strategy|planning|analysis|fundamentals?|basics?)\b',

            # Training methodologies
            r'\b(?:role.?play|simulation|case study|workshop|training|assessment|evaluation|feedback)\s+(?:techniques?|methods?|approaches?|strategies?)\b',
            r'\b(?:learning|teaching|instructional|educational)\s+(?:objectives?|methods?|strategies?|design|techniques?)\b',

            # Health and safety
            r'\b(?:safety|health|medical|clinical|patient)\s+(?:procedures?|protocols?|guidelines?|training|care|management)\b',
            r'\b(?:first aid|cpr|emergency|wellness|nutrition|fitness)\s+(?:training|procedures?|basics?|fundamentals?)\b'
        ]

        # Extract patterns
        for pattern in training_concept_patterns:
            matches = re.finditer(pattern, transcript, re.IGNORECASE)
            for match in matches:
                concept = match.group(0).strip()
                # Clean up and standardize the concept
                concept = re.sub(r'\s+', ' ', concept)
                if len(concept) > 3:
                    training_topics.add(concept.title())

        # Context-specific analysis based on keywords
        context_analysis = self._analyze_training_context(transcript)
        if context_analysis:
            training_topics.update(context_analysis)

        # Extract role-play and simulation topics
        roleplay_topics = self._extract_roleplay_topics(transcript)
        if roleplay_topics:
            training_topics.update(roleplay_topics)

        # Extract process and methodology topics
        process_topics = self._extract_process_topics(transcript)
        if process_topics:
            training_topics.update(process_topics)

        # Format the result
        if training_topics:
            topic_list = sorted(list(training_topics))[:10]  # Top 10 topics
            return f"Training Topics: {', '.join(topic_list)}"
        else:
            # Fallback to identifying general subject area
            return self._identify_general_subject(transcript)

    def _analyze_training_context(self, transcript: str) -> Set[str]:
        """Analyze context to identify specific training domains"""
        topics = set()
        text_lower = transcript.lower()

        # Technology training indicators
        if any(term in text_lower for term in ['code', 'programming', 'development', 'software', 'api', 'database']):
            if 'java' in text_lower:
                topics.add('Java Programming')
            if 'python' in text_lower:
                topics.add('Python Development')
            if 'web' in text_lower:
                topics.add('Web Development')
            if 'database' in text_lower:
                topics.add('Database Management')

        # Business training indicators
        if any(term in text_lower for term in ['client', 'customer', 'business', 'sales', 'management']):
            if 'client' in text_lower and 'engagement' in text_lower:
                topics.add('Client Engagement Strategies')
            if 'project' in text_lower:
                topics.add('Project Management')
            if 'leadership' in text_lower:
                topics.add('Leadership Skills')

        return topics

    def _extract_roleplay_topics(self, transcript: str) -> Set[str]:
        """Extract topics from role-play scenarios"""
        topics = set()
        text_lower = transcript.lower()

        # Role-play scenario analysis
        if 'role play' in text_lower or 'roleplay' in text_lower:
            topics.add('Role-Playing Techniques')

            # Specific role-play contexts
            if 'client' in text_lower:
                topics.add('Client Interaction Simulation')
            if 'problem' in text_lower and 'solving' in text_lower:
                topics.add('Problem Resolution Skills')
            if 'team' in text_lower:
                topics.add('Team Collaboration')
            if 'assessment' in text_lower:
                topics.add('Performance Assessment')

        return topics

    def _extract_process_topics(self, transcript: str) -> Set[str]:
        """Extract process and methodology topics"""
        topics = set()
        text_lower = transcript.lower()

        # Process keywords
        process_indicators = [
            ('implementation', 'Implementation Strategies'),
            ('migration', 'System Migration'),
            ('integration', 'System Integration'),
            ('testing', 'Testing Methodologies'),
            ('deployment', 'Deployment Processes'),
            ('workflow', 'Workflow Management'),
            ('methodology', 'Process Methodologies')
        ]

        for keyword, topic in process_indicators:
            if keyword in text_lower:
                topics.add(topic)

        return topics

    def _identify_general_subject(self, transcript: str) -> str:
        """Fallback method to identify general subject area"""
        text_lower = transcript.lower()

        # Subject area mapping
        subjects = {
            'technology': ['programming', 'software', 'development', 'code', 'api', 'database', 'system'],
            'business': ['management', 'leadership', 'client', 'customer', 'sales', 'marketing', 'strategy'],
            'communication': ['presentation', 'speaking', 'communication', 'negotiation', 'discussion'],
            'training': ['training', 'learning', 'education', 'teaching', 'instruction', 'assessment'],
            'project management': ['project', 'planning', 'coordination', 'timeline', 'delivery', 'stakeholder']
        }

        for subject, keywords in subjects.items():
            if sum(1 for keyword in keywords if keyword in text_lower) >= 2:
                return f"{subject.title()} Training Concepts"

        return "Professional Development Training"

    def extract_instructor_name(self, transcript: str) -> Optional[str]:
        """Extract instructor name using multiple patterns"""
        if not transcript:
            return None

        # Try each pattern
        for pattern in self.instructor_patterns:
            match = re.search(pattern, transcript, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Validate the name
                if self._is_valid_name(name):
                    return name

        return None

    def _is_valid_name(self, name: str) -> bool:
        """Validate if extracted text is likely a real name"""
        if not name or len(name) < 3 or len(name) > 50:
            return False

        # Should have at least 2 words
        words = name.split()
        if len(words) < 2:
            return False

        # Each word should start with capital letter
        if not all(word[0].isupper() and word[1:].islower() for word in words if word):
            return False

        # Exclude common false positives
        false_positives = [
            'thank you', 'good morning', 'good afternoon', 'good evening',
            'welcome back', 'let me', 'going to', 'able to', 'want to'
        ]

        name_lower = name.lower()
        if any(fp in name_lower for fp in false_positives):
            return False

        return True

    def detect_category(self, transcript: str, filename: str = "") -> str:
        """Detect content category from transcript and filename"""
        text = (transcript + " " + filename).lower()

        category_scores = {}

        for category, patterns in self.topic_patterns.items():
            score = 0
            for pattern in patterns:
                matches = len(re.findall(pattern, text, re.IGNORECASE))
                score += matches
            category_scores[category] = score

        if category_scores and max(category_scores.values()) > 0:
            return max(category_scores, key=category_scores.get)

        return "Unknown"

    def calculate_confidence(self, instructor_found: bool, topics_extracted: bool, transcript_length: int) -> float:
        """Calculate confidence score based on extraction success"""
        base_score = 0.3

        if instructor_found:
            base_score += 0.3

        if topics_extracted:
            base_score += 0.3

        # Bonus for good transcript length
        if transcript_length > 500:
            base_score += 0.1
        elif transcript_length > 1000:
            base_score += 0.2

        return min(1.0, base_score)
