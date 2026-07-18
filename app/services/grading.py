from typing import List, Optional, Any

def grade_question(question: dict, answer: Any, marks_to_cut: float = 0) -> dict:
    """
    Return { "is_correct": bool | None, "marks_earned": float }
    
    - Choices: matches option index with is_correct_1..4
      If question.multiple=True, all correct must be selected
      If negative marking, wrong answer -> -marks_to_cut
    - User Input: matches answer (case-insensitive trim) with possibility_1..4
    - Open Ended: returns is_correct=None, marks_earned=0 (pending review)
    """
    q_type = question.get("type", "Choices")
    marks = float(question.get("marks", 1))
    
    if q_type == "Choices":
        is_multiple = question.get("multiple", False)
        
        # Get correct options
        correct_options = []
        for i in range(1, 5):
            if question.get(f"is_correct_{i}"):
                correct_options.append(str(i))
        
        # Handle student answer
        student_answers = []
        if isinstance(answer, list):
            student_answers = [str(a) for a in answer]
        elif isinstance(answer, str):
            # Split by comma or handle as single
            student_answers = [a.strip() for a in answer.split(",") if a.strip()]
        else:
            student_answers = [str(answer)]
            
        is_correct = False
        if is_multiple:
            # All correct must be selected, and no incorrect must be selected
            is_correct = set(student_answers) == set(correct_options)
        else:
            # Single choice
            if len(student_answers) == 1:
                is_correct = student_answers[0] in correct_options
            else:
                is_correct = False
        
        if is_correct:
            return {"is_correct": True, "marks_earned": marks}
        else:
            return {"is_correct": False, "marks_earned": -float(marks_to_cut)}
            
    elif q_type == "User Input":
        if not answer:
            return {"is_correct": False, "marks_earned": -float(marks_to_cut)}
            
        student_ans = str(answer).strip().lower()
        possibilities = []
        for i in range(1, 5):
            p = question.get(f"possibility_{i}")
            if p:
                possibilities.append(p.strip().lower())
        
        if student_ans in possibilities:
            return {"is_correct": True, "marks_earned": marks}
        else:
            return {"is_correct": False, "marks_earned": -float(marks_to_cut)}
            
    elif q_type == "Open Ended":
        return {"is_correct": None, "marks_earned": 0.0}
        
    return {"is_correct": False, "marks_earned": 0.0}

def calculate_total_marks(questions: list, limit_questions_to: Optional[int] = None) -> float:
    """Sum of all question marks (or baseline * limit if shuffle/limit enabled)"""
    if not questions:
        return 0.0
    
    if limit_questions_to and limit_questions_to > 0:
        marks = float(questions[0].get("marks", 1))
        return marks * limit_questions_to
        
    return sum(float(q.get("marks", 1)) for q in questions)

def check_passing(percentage: float, passing_percentage: float) -> bool:
    """percentage >= passing_percentage"""
    return percentage >= passing_percentage
