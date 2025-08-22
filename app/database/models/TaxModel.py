from pydantic import BaseModel, Field, validator, root_validator
from typing import Any, Dict, Literal, Optional, List
from uuid import uuid4
from datetime import date
import re
from pydantic import BaseModel, Field
from typing import Optional
from pydantic import BaseModel, Field
import datetime
from uuid import uuid4
from typing import Optional

class TaxComponent(BaseModel):
    name: str              
    rate: float            
    rate_type: Literal["percentage", "fixed"] = "percentage"
    
class TaxDependency(BaseModel):
    depends_on_tax_id: str
    dependency_type: Literal["on_base", "on_tax_amount"] = "on_tax_amount" 
    rate: Optional[float] = None 
    
class TaxModel(BaseModel):
    tax_name: str
    tax_code: str
    tax_description: Optional[str] = None
    jurisdiction: List[str] # e.g., ["+91", "+1"]
    tax_type: Literal["GST", "VAT", "Service Tax", "Cess", "Custom Duty", "Excise Duty", "Sales Tax", "Other"] = "GST"
    tax_rate: float
    tax_rate_type: Literal["percentage", "fixed"] = "percentage"
    components: Optional[List[TaxComponent]] = None
    dependencies: Optional[List[TaxDependency]] = None
    
class TaxModelDB(TaxModel):
    tax_model_id: str = Field(default_factory=lambda: str(uuid4()), alias="_id")
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.now)
    